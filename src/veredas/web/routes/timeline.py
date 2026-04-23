"""
Rota de timeline de eventos regulatorios.

Exibe historico de eventos:
- Intervencoes do Banco Central
- Casos historicos (Master, BVA, etc.)
- Anomalias significativas
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from veredas.storage.models import Severidade
from veredas.storage.repository import AnomaliaRepository, EventoRegulatorioRepository
from veredas.web.app import templates
from veredas.web.dependencies import get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def timeline_view(
    request: Request,
    session=Depends(get_db),
    ano: int | None = Query(None, description="Filtrar por ano"),
    tipo: str | None = Query(None, description="Filtrar por tipo de evento"),
    pagina: int = Query(1, ge=1, description="Pagina atual"),
    por_pagina: int = Query(20, ge=10, le=100, description="Itens por pagina"),
):
    """
    Timeline de eventos regulatorios e anomalias historicas.
    """
    evento_repo = EventoRegulatorioRepository(session)
    anomalia_repo = AnomaliaRepository(session)

    # Buscar eventos regulatorios (limitado para paginacao)
    filters = {}
    if ano:
        filters["ano"] = ano
    if tipo:
        filters["tipo"] = tipo

    # Limitar busca inicial para memoria
    max_items = por_pagina * 5  # Buscar 5 paginas de cada fonte no maximo
    eventos = evento_repo.list_with_filters(
        filters=filters, order_by="data_desc", limit=max_items, eager_load=True
    )

    # Anomalias criticas historicas (com eager loading e limite)
    anomalias_criticas = anomalia_repo.list_with_filters(
        filters={"severidade": Severidade.CRITICAL},
        limit=max_items,
        eager_load=True,
    )

    # Combinar em timeline ordenada
    all_items = _build_timeline(eventos, anomalias_criticas)
    total = len(all_items)
    total_paginas = (total + por_pagina - 1) // por_pagina

    # Aplicar paginacao
    offset = (pagina - 1) * por_pagina
    timeline_items = all_items[offset : offset + por_pagina]

    # Anos disponiveis para filtro
    anos = evento_repo.get_distinct_years()

    # Tipos de evento disponiveis
    tipos = evento_repo.get_distinct_types()

    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "timeline_items": timeline_items,
            "total": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "anos": anos,
            "tipos": tipos,
            "filtros": {
                "ano": ano,
                "tipo": tipo,
            },
        },
    )


def _build_timeline(eventos: list, anomalias: list) -> list[dict]:
    """
    Combina eventos e anomalias em timeline ordenada.

    Args:
        eventos: Lista de eventos regulatorios.
        anomalias: Lista de anomalias criticas.

    Returns:
        Lista de items ordenados por data (mais recente primeiro).
    """
    items = []

    # Adicionar eventos
    for evento in eventos:
        items.append(
            {
                "type": "evento",
                "date": evento.data_evento,
                "title": f"{evento.tipo.value} - {evento.if_nome}",
                "description": evento.descricao,
                "severity": evento.tipo.value,
                "source": evento.fonte,
                "instituicao": evento.instituicao.nome if evento.instituicao else evento.if_nome,
            }
        )

    # Adicionar anomalias
    for anomalia in anomalias:
        items.append(
            {
                "type": "anomalia",
                "date": anomalia.detectado_em.date() if anomalia.detectado_em else None,
                "title": f"Anomalia: {anomalia.tipo.value}",
                "description": anomalia.descricao,
                "severity": anomalia.severidade.value,
                "source": "veredas",
                "instituicao": anomalia.instituicao.nome if anomalia.instituicao else None,
            }
        )

    # Ordenar por data (mais recente primeiro)
    items.sort(key=lambda x: x["date"] if x["date"] else date.min, reverse=True)

    return items


@router.get("/eventos/{evento_id}", response_class=HTMLResponse)
async def evento_detail(
    request: Request,
    evento_id: int,
    session=Depends(get_db),
):
    """
    Detalhe de um evento regulatorio.
    """
    evento_repo = EventoRegulatorioRepository(session)

    evento = evento_repo.get_by_id(evento_id)
    if not evento:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"message": "Evento nao encontrado"},
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "evento.html",
        {
            "evento": evento,
        },
    )
