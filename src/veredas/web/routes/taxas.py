"""
Rota da pagina de taxas de CDB.

Exibe tabela filtravel de taxas coletadas:
- Filtros: indexador, prazo, IF (via HTMX)
- Ordenacao por spread, data, valor
- Paginacao server-side
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse

from veredas.web.app import templates
from veredas.storage.database import DatabaseManager
from veredas.storage.repository import TaxaCDBRepository, InstituicaoRepository
from veredas.storage.models import Indexador

router = APIRouter()


def get_db():
    """Dependencia para obter sessao do banco."""
    from veredas.config import get_settings

    settings = get_settings()
    db_manager = DatabaseManager(settings.database.path)

    with db_manager.session_scope() as session:
        yield session


@router.get("/", response_class=HTMLResponse)
async def list_taxas(
    request: Request,
    session=Depends(get_db),
    indexador: Optional[str] = Query(None, description="Filtrar por indexador"),
    prazo_min: Optional[int] = Query(None, description="Prazo minimo em dias"),
    prazo_max: Optional[int] = Query(None, description="Prazo maximo em dias"),
    if_id: Optional[int] = Query(None, description="ID da instituicao"),
    ordem: str = Query("data_desc", description="Ordenacao"),
    pagina: int = Query(1, ge=1, description="Pagina"),
    por_pagina: int = Query(20, ge=10, le=100, description="Itens por pagina"),
):
    """
    Lista taxas de CDB com filtros e paginacao.
    """
    taxa_repo = TaxaCDBRepository(session)
    if_repo = InstituicaoRepository(session)

    # Aplicar filtros
    filters = {}
    if indexador:
        filters["indexador"] = Indexador(indexador)
    if prazo_min:
        filters["prazo_min"] = prazo_min
    if prazo_max:
        filters["prazo_max"] = prazo_max
    if if_id:
        filters["instituicao_id"] = if_id

    # Obter taxas com paginacao
    taxas, total = taxa_repo.list_paginated(
        filters=filters,
        order_by=ordem,
        page=pagina,
        per_page=por_pagina,
    )

    # Calcular paginacao
    total_paginas = (total + por_pagina - 1) // por_pagina

    # Listar IFs para filtro
    instituicoes = if_repo.list_all()

    # Opcoes de indexador
    indexadores = [e.value for e in Indexador]

    context = {
        "request": request,
        "taxas": taxas,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
        "indexador": indexador,
        "prazo_min": prazo_min,
        "prazo_max": prazo_max,
        "if_id": if_id,
        "ordem": ordem,
        "instituicoes": instituicoes,
        "indexadores": indexadores,
    }

    # Se for request HTMX, retornar apenas a tabela
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/taxas_table.html", context)

    return templates.TemplateResponse("taxas.html", context)


@router.get("/{taxa_id}", response_class=HTMLResponse)
async def get_taxa(
    request: Request,
    taxa_id: int,
    session=Depends(get_db),
):
    """
    Detalhe de uma taxa especifica.
    """
    taxa_repo = TaxaCDBRepository(session)
    taxa = taxa_repo.get_by_id(taxa_id)

    if not taxa:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Taxa nao encontrada"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "taxa_detail.html",
        {
            "request": request,
            "taxa": taxa,
        },
    )
