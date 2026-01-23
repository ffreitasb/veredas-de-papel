"""
Rota de anomalias detectadas.

Exibe lista de anomalias:
- Filtros: severidade, tipo, instituicao
- Acoes: marcar como resolvida
- Historico de anomalias
"""

from typing import Optional

from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.responses import HTMLResponse

from veredas.web.app import templates
from veredas.web.dependencies import get_db
from veredas.storage.repository import AnomaliaRepository, InstituicaoFinanceiraRepository
from veredas.storage.models import Severidade

router = APIRouter()


def _parse_severidade(value: Optional[str]) -> Optional[Severidade]:
    """
    Converte string para Severidade enum de forma segura.

    Args:
        value: Valor string da severidade.

    Returns:
        Severidade enum ou None se valor vazio.

    Raises:
        HTTPException: Se valor invalido.
    """
    if not value:
        return None

    try:
        return Severidade(value)
    except ValueError:
        valid_values = [s.value for s in Severidade]
        raise HTTPException(
            status_code=400,
            detail=f"Severidade invalida: '{value}'. Valores aceitos: {valid_values}",
        )


@router.get("/", response_class=HTMLResponse)
async def anomalias_list(
    request: Request,
    session=Depends(get_db),
    severidade: Optional[str] = Query(None, description="Filtro por severidade"),
    tipo: Optional[str] = Query(None, description="Filtro por tipo de anomalia"),
    instituicao: Optional[str] = Query(None, description="Filtro por CNPJ da IF"),
    status: str = Query("ativas", description="ativas ou todas"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=10, le=100),
):
    """
    Listagem de anomalias detectadas.
    """
    anomalia_repo = AnomaliaRepository(session)
    if_repo = InstituicaoFinanceiraRepository(session)

    # Construir filtros (com validacao segura de enum)
    filters = {}
    parsed_severidade = _parse_severidade(severidade)
    if parsed_severidade:
        filters["severidade"] = parsed_severidade
    if tipo:
        filters["tipo"] = tipo
    if instituicao:
        filters["cnpj"] = instituicao
    if status == "ativas":
        filters["resolvida"] = False

    # Buscar anomalias (com eager loading para evitar N+1)
    offset = (pagina - 1) * por_pagina
    anomalias = anomalia_repo.list_with_filters(
        filters=filters,
        limit=por_pagina,
        offset=offset,
        eager_load=True,
    )
    total = anomalia_repo.count_with_filters(filters=filters)
    total_paginas = (total + por_pagina - 1) // por_pagina

    # Dados para filtros
    instituicoes = if_repo.list_all()
    severidades = [s.value for s in Severidade]
    tipos = anomalia_repo.get_distinct_tipos()

    return templates.TemplateResponse(
        "anomalias.html",
        {
            "request": request,
            "anomalias": anomalias,
            "total": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "instituicoes": instituicoes,
            "severidades": severidades,
            "tipos": tipos,
            "filtros": {
                "severidade": severidade,
                "tipo": tipo,
                "instituicao": instituicao,
                "status": status,
            },
        },
    )


@router.post("/{anomalia_id}/resolver", response_class=HTMLResponse)
async def resolver_anomalia(
    request: Request,
    anomalia_id: int,
    session=Depends(get_db),
    notas: str = Form(""),
):
    """
    Marca uma anomalia como resolvida (HTMX POST).
    """
    anomalia_repo = AnomaliaRepository(session)

    anomalia = anomalia_repo.get_by_id(anomalia_id)
    if anomalia:
        anomalia_repo.mark_resolved(anomalia_id, notas=notas)

    # Retorna partial atualizado
    return templates.TemplateResponse(
        "partials/anomalia_card.html",
        {
            "request": request,
            "anomalia": anomalia,
            "resolved": True,
        },
    )


@router.get("/partials/list", response_class=HTMLResponse)
async def anomalias_list_partial(
    request: Request,
    session=Depends(get_db),
    severidade: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    instituicao: Optional[str] = Query(None),
    status: str = Query("ativas"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=10, le=100),
):
    """
    Partial HTMX para lista de anomalias.
    """
    anomalia_repo = AnomaliaRepository(session)

    # Construir filtros (com validacao segura de enum)
    filters = {}
    parsed_severidade = _parse_severidade(severidade)
    if parsed_severidade:
        filters["severidade"] = parsed_severidade
    if tipo:
        filters["tipo"] = tipo
    if instituicao:
        filters["cnpj"] = instituicao
    if status == "ativas":
        filters["resolvida"] = False

    offset = (pagina - 1) * por_pagina
    anomalias = anomalia_repo.list_with_filters(
        filters=filters,
        limit=por_pagina,
        offset=offset,
    )
    total = anomalia_repo.count_with_filters(filters=filters)
    total_paginas = (total + por_pagina - 1) // por_pagina

    return templates.TemplateResponse(
        "partials/anomalias_list.html",
        {
            "request": request,
            "anomalias": anomalias,
            "total": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
        },
    )
