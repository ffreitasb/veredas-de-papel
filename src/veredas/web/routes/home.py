"""
Rota da pagina inicial (dashboard).

Exibe visao geral do sistema:
- Taxas de referencia atuais (Selic, CDI, IPCA)
- Contagem de anomalias por severidade
- Ultimas anomalias detectadas
- Status do sistema
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from veredas.storage.models import Severidade
from veredas.storage.repository import (
    AnomaliaRepository,
    TaxaCDBRepository,
)
from veredas.web.cache import get_cached_reference_rates
from veredas.web.dependencies import get_db
from veredas.web.templates_config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, session=Depends(get_db)):
    """
    Pagina inicial com visao geral do sistema.
    """
    # Repositories
    anomalia_repo = AnomaliaRepository(session)
    taxa_cdb_repo = TaxaCDBRepository(session)

    # Taxas de referencia atuais (cache de 1 hora)
    rates = get_cached_reference_rates(session)
    selic = rates.get("selic")
    cdi = rates.get("cdi")
    ipca = rates.get("ipca")

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
        request,
        "index.html",
        {
            "taxas_referencia": taxas_referencia,
            "anomalias_count": anomalias_count,
            "ultimas_anomalias": ultimas_anomalias,
            "total_taxas": total_taxas,
            "total_ifs": total_ifs,
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
        request,
        "partials/stats_cards.html",
        {
            "anomalias_count": anomalias_count,
        },
    )
