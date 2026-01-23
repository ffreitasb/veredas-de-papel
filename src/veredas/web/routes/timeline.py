"""
Rota de timeline de eventos regulatorios.

Exibe historico de eventos:
- Intervencoes do Banco Central
- Casos historicos (Master, BVA, etc.)
- Anomalias significativas
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse

from veredas.web.app import templates
from veredas.storage.database import DatabaseManager
from veredas.storage.repository import EventoRegulatorioRepository, AnomaliaRepository
from veredas.storage.models import Severidade

router = APIRouter()


def get_db():
    """Dependencia para obter sessao do banco."""
    from veredas.config import get_settings

    settings = get_settings()
    db_manager = DatabaseManager(settings.database.path)

    with db_manager.session_scope() as session:
        yield session


@router.get("/", response_class=HTMLResponse)
async def timeline_view(
    request: Request,
    session=Depends(get_db),
    ano: Optional[int] = Query(None, description="Filtrar por ano"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de evento"),
):
    """
    Timeline de eventos regulatorios e anomalias historicas.
    """
    evento_repo = EventoRegulatorioRepository(session)
    anomalia_repo = AnomaliaRepository(session)

    # Buscar eventos regulatorios
    filters = {}
    if ano:
        filters["ano"] = ano
    if tipo:
        filters["tipo"] = tipo

    eventos = evento_repo.list_with_filters(filters=filters, order_by="data_desc")

    # Anomalias criticas historicas
    anomalias_criticas = anomalia_repo.list_with_filters(
        filters={"severidade": Severidade.CRITICAL},
        limit=50,
    )

    # Combinar em timeline ordenada
    timeline_items = _build_timeline(eventos, anomalias_criticas)

    # Anos disponiveis para filtro
    anos = evento_repo.get_distinct_years()

    # Tipos de evento disponiveis
    tipos = evento_repo.get_distinct_types()

    return templates.TemplateResponse(
        "timeline.html",
        {
            "request": request,
            "timeline_items": timeline_items,
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
        items.append({
            "type": "evento",
            "date": evento.data_evento,
            "title": f"{evento.tipo.value} - {evento.if_nome}",
            "description": evento.descricao,
            "severity": evento.tipo.value,
            "source": evento.fonte,
            "instituicao": evento.instituicao.nome if evento.instituicao else evento.if_nome,
        })

    # Adicionar anomalias
    for anomalia in anomalias:
        items.append({
            "type": "anomalia",
            "date": anomalia.detectado_em.date() if anomalia.detectado_em else None,
            "title": f"Anomalia: {anomalia.tipo.value}",
            "description": anomalia.descricao,
            "severity": anomalia.severidade.value,
            "source": "veredas",
            "instituicao": anomalia.instituicao.nome if anomalia.instituicao else None,
        })

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
            "errors/404.html",
            {"request": request, "message": "Evento nao encontrado"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "evento.html",
        {
            "request": request,
            "evento": evento,
        },
    )
