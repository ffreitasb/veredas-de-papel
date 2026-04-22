"""
Rota da pagina de taxas de CDB.

Exibe tabela filtravel de taxas coletadas:
- Filtros: indexador, prazo, IF (via HTMX)
- Ordenacao por spread, data, valor
- Paginacao server-side
"""

import csv
import io

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from veredas.storage.models import Indexador
from veredas.storage.repository import InstituicaoRepository, TaxaCDBRepository
from veredas.web.app import templates
from veredas.web.dependencies import get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_taxas(
    request: Request,
    session=Depends(get_db),
    indexador: str | None = Query(None, description="Filtrar por indexador"),
    prazo_min: int | None = Query(None, description="Prazo minimo em dias"),
    prazo_max: int | None = Query(None, description="Prazo maximo em dias"),
    if_id: int | None = Query(None, description="ID da instituicao"),
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


@router.get("/export.csv")
async def export_taxas_csv(
    session=Depends(get_db),
    indexador: str | None = Query(None),
    prazo_min: int | None = Query(None),
    prazo_max: int | None = Query(None),
    if_id: int | None = Query(None),
    ordem: str = Query("data_desc"),
):
    """Exporta taxas filtradas como CSV (UTF-8-BOM, compatível com Excel)."""
    taxa_repo = TaxaCDBRepository(session)

    filters = {}
    if indexador:
        filters["indexador"] = Indexador(indexador)
    if prazo_min:
        filters["prazo_min"] = prazo_min
    if prazo_max:
        filters["prazo_max"] = prazo_max
    if if_id:
        filters["instituicao_id"] = if_id

    # Exporta até 10 000 linhas sem paginação
    taxas, _ = taxa_repo.list_paginated(filters=filters, order_by=ordem, page=1, per_page=10_000)

    def _gerar_csv():
        buf = io.StringIO()
        buf.write("\ufeff")  # UTF-8 BOM para Excel brasileiro
        writer = csv.writer(buf, delimiter=";")
        writer.writerow([
            "Data Coleta", "Instituição", "CNPJ", "Indexador",
            "Percentual (%)", "Taxa Adicional (%)", "Prazo (dias)",
            "Liquidez Diária", "Fonte", "Risk Score",
        ])
        yield buf.getvalue()

        for taxa in taxas:
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter=";")
            writer.writerow([
                taxa.data_coleta.strftime("%d/%m/%Y"),
                taxa.instituicao.nome if taxa.instituicao else "",
                taxa.instituicao.cnpj if taxa.instituicao else "",
                taxa.indexador.value,
                str(taxa.percentual).replace(".", ","),
                str(taxa.taxa_adicional).replace(".", ",") if taxa.taxa_adicional else "",
                taxa.prazo_dias,
                "Sim" if taxa.liquidez_diaria else "Não",
                taxa.fonte,
                str(taxa.risk_score).replace(".", ",") if taxa.risk_score else "",
            ])
            yield buf.getvalue()

    return StreamingResponse(
        _gerar_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=taxas_cdb.csv"},
    )


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
