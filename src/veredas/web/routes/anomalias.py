"""
Rota de anomalias detectadas.

Exibe lista de anomalias:
- Filtros: severidade, tipo, instituicao
- Acoes: marcar como resolvida
- Historico de anomalias
"""

import csv
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from veredas.storage.models import Severidade
from veredas.storage.repository import AnomaliaRepository, InstituicaoFinanceiraRepository
from veredas.web.app import templates
from veredas.web.dependencies import get_db

router = APIRouter()


def _parse_severidade(value: str | None) -> Severidade | None:
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
        ) from None


@router.get("/", response_class=HTMLResponse)
async def anomalias_list(
    request: Request,
    session=Depends(get_db),
    severidade: str | None = Query(None, description="Filtro por severidade"),
    tipo: str | None = Query(None, description="Filtro por tipo de anomalia"),
    instituicao: str | None = Query(None, description="Filtro por CNPJ da IF"),
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
        filters["resolvido"] = False

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
        request,
        "anomalias.html",
        {
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


@router.get("/export.csv")
async def export_anomalias_csv(
    session=Depends(get_db),
    severidade: str | None = Query(None),
    tipo: str | None = Query(None),
    instituicao: str | None = Query(None),
    status: str = Query("ativas"),
):
    """Exporta anomalias filtradas como CSV (UTF-8-BOM, compatível com Excel)."""
    anomalia_repo = AnomaliaRepository(session)

    filters: dict = {}
    parsed_sev = _parse_severidade(severidade)
    if parsed_sev:
        filters["severidade"] = parsed_sev
    if tipo:
        filters["tipo"] = tipo
    if instituicao:
        filters["cnpj"] = instituicao
    if status == "ativas":
        filters["resolvido"] = False

    anomalias = anomalia_repo.list_with_filters(
        filters=filters, limit=10_000, offset=0, eager_load=True
    )

    def _gerar_csv():
        buf = io.StringIO()
        buf.write("\ufeff")  # UTF-8 BOM para Excel brasileiro
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(
            [
                "ID",
                "Tipo",
                "Severidade",
                "Instituição",
                "CNPJ",
                "Valor Detectado",
                "Valor Esperado",
                "Desvio",
                "Descrição",
                "Detectado Em",
                "Resolvido",
                "Resolvido Em",
            ]
        )
        yield buf.getvalue()

        for a in anomalias:
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter=";")
            writer.writerow(
                [
                    a.id,
                    a.tipo.value,
                    a.severidade.value,
                    a.instituicao.nome if a.instituicao else "",
                    a.instituicao.cnpj if a.instituicao else "",
                    str(a.valor_detectado).replace(".", ","),
                    str(a.valor_esperado).replace(".", ",") if a.valor_esperado else "",
                    str(a.desvio).replace(".", ",") if a.desvio else "",
                    a.descricao,
                    a.detectado_em.strftime("%d/%m/%Y %H:%M") if a.detectado_em else "",
                    "Sim" if a.resolvido else "Não",
                    a.resolvido_em.strftime("%d/%m/%Y %H:%M") if a.resolvido_em else "",
                ]
            )
            yield buf.getvalue()

    return StreamingResponse(
        _gerar_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=anomalias.csv"},
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
        request,
        "partials/anomalia_card.html",
        {
            "anomalia": anomalia,
            "resolved": True,
        },
    )


@router.get("/partials/list", response_class=HTMLResponse)
async def anomalias_list_partial(
    request: Request,
    session=Depends(get_db),
    severidade: str | None = Query(None),
    tipo: str | None = Query(None),
    instituicao: str | None = Query(None),
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
        filters["resolvido"] = False

    offset = (pagina - 1) * por_pagina
    anomalias = anomalia_repo.list_with_filters(
        filters=filters,
        limit=por_pagina,
        offset=offset,
    )
    total = anomalia_repo.count_with_filters(filters=filters)
    total_paginas = (total + por_pagina - 1) // por_pagina

    return templates.TemplateResponse(
        request,
        "partials/anomalias_list.html",
        {
            "anomalias": anomalias,
            "total": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "filtros": {
                "severidade": severidade,
                "tipo": tipo,
                "instituicao": instituicao,
                "status": status,
            },
        },
    )
