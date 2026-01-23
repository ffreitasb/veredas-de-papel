"""
Rota de instituicoes financeiras.

Exibe lista de IFs monitoradas:
- Indicadores: Basileia, Liquidez
- Score de risco composto
- Historico de taxas
"""

from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse

from veredas.web.app import templates
from veredas.web.dependencies import get_db
from veredas.storage.repository import (
    InstituicaoFinanceiraRepository,
    TaxaCDBRepository,
    AnomaliaRepository,
)
from veredas.validators import parse_cnpj

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def instituicoes_list(
    request: Request,
    session=Depends(get_db),
    ordem: str = Query("nome", description="Ordenacao: nome, risco, basileia"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(30, ge=10, le=100),
):
    """
    Lista de instituicoes financeiras monitoradas.
    """
    if_repo = InstituicaoFinanceiraRepository(session)

    offset = (pagina - 1) * por_pagina
    instituicoes = if_repo.list_paginated(
        order_by=ordem,
        limit=por_pagina,
        offset=offset,
    )
    total = if_repo.count()
    total_paginas = (total + por_pagina - 1) // por_pagina

    return templates.TemplateResponse(
        "instituicoes.html",
        {
            "request": request,
            "instituicoes": instituicoes,
            "total": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "ordem": ordem,
        },
    )


@router.get("/{cnpj}", response_class=HTMLResponse)
async def instituicao_detail(
    request: Request,
    cnpj: str,
    session=Depends(get_db),
):
    """
    Detalhe de uma instituicao financeira.

    Mostra:
    - Dados cadastrais
    - Indicadores de saude (Basileia, Liquidez)
    - Historico de taxas
    - Anomalias relacionadas
    """
    # Validar e normalizar CNPJ (levanta HTTPException se invalido)
    cnpj_normalizado = parse_cnpj(cnpj, required=True, validate=False)

    if_repo = InstituicaoFinanceiraRepository(session)
    taxa_repo = TaxaCDBRepository(session)
    anomalia_repo = AnomaliaRepository(session)

    # Buscar IF
    instituicao = if_repo.get_by_cnpj(cnpj_normalizado)
    if not instituicao:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Instituicao nao encontrada"},
            status_code=404,
        )

    # Historico de taxas (ultimos 30 dias)
    taxas = taxa_repo.get_by_instituicao(
        instituicao_id=instituicao.id,
        limit=100,
    )

    # Anomalias relacionadas
    anomalias = anomalia_repo.get_by_instituicao(instituicao.id, limit=20)

    # Dados para grafico de evolucao
    chart_data = _prepare_chart_data(taxas)

    return templates.TemplateResponse(
        "instituicao.html",
        {
            "request": request,
            "instituicao": instituicao,
            "taxas": taxas,
            "anomalias": anomalias,
            "chart_data": chart_data,
        },
    )


def _prepare_chart_data(taxas: list) -> dict:
    """
    Prepara dados para grafico Plotly de evolucao de taxas.

    Args:
        taxas: Lista de taxas da instituicao.

    Returns:
        Dicionario com dados formatados para Plotly.
    """
    if not taxas:
        return {"dates": [], "values": [], "labels": []}

    dates = []
    values = []
    labels = []

    for taxa in sorted(taxas, key=lambda t: t.data_coleta):
        dates.append(taxa.data_coleta.isoformat())
        values.append(float(taxa.percentual))
        labels.append(f"{taxa.indexador.value} - {taxa.prazo_dias}d")

    return {
        "dates": dates,
        "values": values,
        "labels": labels,
    }


@router.get("/partials/chart/{cnpj}", response_class=HTMLResponse)
async def instituicao_chart_partial(
    request: Request,
    cnpj: str,
    session=Depends(get_db),
):
    """
    Partial HTMX para grafico de evolucao da IF.
    """
    # Validar e normalizar CNPJ
    cnpj_normalizado = parse_cnpj(cnpj, required=True, validate=False)

    if_repo = InstituicaoFinanceiraRepository(session)
    taxa_repo = TaxaCDBRepository(session)

    instituicao = if_repo.get_by_cnpj(cnpj_normalizado)
    if not instituicao:
        return HTMLResponse("<p>IF nao encontrada</p>", status_code=404)

    taxas = taxa_repo.get_by_instituicao(instituicao_id=instituicao.id, limit=100)
    chart_data = _prepare_chart_data(taxas)

    return templates.TemplateResponse(
        "partials/instituicao_chart.html",
        {
            "request": request,
            "instituicao": instituicao,
            "chart_data": chart_data,
        },
    )
