"""
Rota da pagina inicial (dashboard).

Exibe visao geral do sistema:
- Taxas de referencia atuais (Selic, CDI, IPCA)
- Contagem de anomalias por severidade
- Ultimas anomalias detectadas
- Status do sistema
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from veredas.web.app import templates
from veredas.storage.database import DatabaseManager, get_session
from veredas.storage.repository import (
    TaxaReferenciaRepository,
    AnomaliaRepository,
    TaxaCDBRepository,
)
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
async def home(request: Request, session=Depends(get_db)):
    """
    Pagina inicial com visao geral do sistema.
    """
    # Repositories
    taxa_ref_repo = TaxaReferenciaRepository(session)
    anomalia_repo = AnomaliaRepository(session)
    taxa_cdb_repo = TaxaCDBRepository(session)

    # Taxas de referencia atuais
    selic = taxa_ref_repo.get_latest("selic")
    cdi = taxa_ref_repo.get_latest("cdi")
    ipca = taxa_ref_repo.get_latest("ipca")

    taxas_referencia = {
        "selic": {"valor": selic.valor if selic else None, "data": selic.data if selic else None},
        "cdi": {"valor": cdi.valor if cdi else None, "data": cdi.data if cdi else None},
        "ipca": {"valor": ipca.valor if ipca else None, "data": ipca.data if ipca else None},
    }

    # Contagem de anomalias por severidade
    anomalias_count = {
        "critical": anomalia_repo.count_by_severity(Severidade.CRITICAL),
        "high": anomalia_repo.count_by_severity(Severidade.HIGH),
        "medium": anomalia_repo.count_by_severity(Severidade.MEDIUM),
        "low": anomalia_repo.count_by_severity(Severidade.LOW),
        "total": anomalia_repo.count_active(),
    }

    # Ultimas anomalias
    ultimas_anomalias = anomalia_repo.get_recent(limit=5)

    # Estatisticas de taxas
    total_taxas = taxa_cdb_repo.count()
    total_ifs = taxa_cdb_repo.count_distinct_ifs()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "taxas_referencia": taxas_referencia,
            "anomalias_count": anomalias_count,
            "ultimas_anomalias": ultimas_anomalias,
            "total_taxas": total_taxas,
            "total_ifs": total_ifs,
            "now": datetime.now(),
        },
    )


@router.get("/partials/stats", response_class=HTMLResponse)
async def stats_partial(request: Request, session=Depends(get_db)):
    """
    Partial HTMX para atualizar estatisticas.
    """
    anomalia_repo = AnomaliaRepository(session)

    anomalias_count = {
        "critical": anomalia_repo.count_by_severity(Severidade.CRITICAL),
        "high": anomalia_repo.count_by_severity(Severidade.HIGH),
        "medium": anomalia_repo.count_by_severity(Severidade.MEDIUM),
        "low": anomalia_repo.count_by_severity(Severidade.LOW),
        "total": anomalia_repo.count_active(),
    }

    return templates.TemplateResponse(
        "partials/stats_cards.html",
        {
            "request": request,
            "anomalias_count": anomalias_count,
        },
    )
