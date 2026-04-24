"""Funções auxiliares de coleta — separadas para manter main.py enxuto."""

import asyncio
from pathlib import Path

from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()


def collect_bcb(db_path: Path | None) -> None:
    """Coleta dados do Banco Central."""
    from veredas.collectors.bcb import BCBCollector
    from veredas.storage import DatabaseManager, TaxaReferenciaRepository

    with console.status("[bold blue]Coletando dados do BCB..."):
        collector = BCBCollector()
        result = asyncio.run(collector.collect(dias_retroativos=30))

    if not result.success:
        rprint(f"[red]✗[/] Erro: {result.error}")
        return

    dados = result.data
    table = Table(title="Taxas de Referência - BCB")
    table.add_column("Indicador", style="cyan")
    table.add_column("Valor", style="green")
    table.add_column("Data", style="dim")

    if dados.selic:
        table.add_row("Selic", f"{dados.selic.valor}%", str(dados.selic.data))
    if dados.cdi:
        table.add_row("CDI", f"{dados.cdi.valor}%", str(dados.cdi.data))
    if dados.ipca:
        table.add_row("IPCA", f"{dados.ipca.valor}%", str(dados.ipca.data))

    console.print(table)

    db = DatabaseManager(db_path)
    db.init_db()
    with db.session_scope() as session:
        repo = TaxaReferenciaRepository(session)
        if dados.selic:
            repo.upsert("selic", dados.selic.data, dados.selic.valor, fonte="bcb")
        if dados.cdi:
            repo.upsert("cdi", dados.cdi.data, dados.cdi.valor, fonte="bcb")
        if dados.ipca:
            repo.upsert("ipca", dados.ipca.data, dados.ipca.valor, fonte="bcb")

    rprint("[dim]Dados salvos no banco[/]")


def collect_ifdata(db_path: Path | None) -> None:
    """Coleta dados de saúde financeira do IFData e persiste no banco."""
    from veredas.collectors.ifdata import IFDataCollector
    from veredas.storage import DatabaseManager
    from veredas.storage.repository import HealthDataRepository, InstituicaoRepository

    async def _run():
        async with IFDataCollector() as collector:
            return await collector.collect()

    with console.status("[bold blue]Coletando dados do IFData (BCB)..."):
        result = asyncio.run(_run())

    if not result.success:
        rprint(f"[red]✗[/] Erro IFData: {result.error}")
        return

    dados = result.data
    db = DatabaseManager(db_path)
    db.init_db()

    table = Table(title="Dados de Saúde — IFData")
    table.add_column("Instituição", style="cyan")
    table.add_column("Basileia", justify="right")
    table.add_column("Liquidez", justify="right")
    table.add_column("Ativo Total (R$ mi)", justify="right")

    with db.session_scope() as session:
        if_repo = InstituicaoRepository(session)
        health_repo = HealthDataRepository(session)

        for dados_if in dados.instituicoes:
            if_ = if_repo.upsert(
                cnpj=dados_if.cnpj,
                nome=dados_if.nome,
                indice_basileia=dados_if.indice_basileia,
                indice_liquidez=dados_if.indice_liquidez,
                ativo_total=dados_if.ativo_total,
                patrimonio_liquido=dados_if.patrimonio_liquido,
            )
            health_repo.upsert(
                if_id=if_.id,
                data_base=dados_if.data_base,
                indice_basileia=dados_if.indice_basileia,
                indice_liquidez=dados_if.indice_liquidez,
                ativo_total=dados_if.ativo_total,
                patrimonio_liquido=dados_if.patrimonio_liquido,
                ativos_liquidos=dados_if.ativos_liquidos,
                depositos_totais=dados_if.depositos_totais,
                inadimplencia=dados_if.inadimplencia,
                roa=dados_if.roa,
                roe=dados_if.roe,
            )

            ativo_mi = (
                f"{float(dados_if.ativo_total) / 1_000_000:.1f}" if dados_if.ativo_total else "-"
            )
            basileia = f"{dados_if.indice_basileia:.1f}%" if dados_if.indice_basileia else "-"
            liquidez = f"{dados_if.indice_liquidez:.1f}%" if dados_if.indice_liquidez else "-"
            table.add_row(dados_if.nome[:40], basileia, liquidez, ativo_mi)

    console.print(table)
    rprint(f"[dim]{len(dados.instituicoes)} instituições salvas no banco[/]")


def collect_scrapers(db_path: Path | None, fonte: str = "all") -> None:
    """Coleta prateleiras de CDB das corretoras e persiste no banco."""
    from datetime import datetime

    from veredas import TZ_BRASIL
    from veredas.collectors.scrapers import SCRAPERS, get_collector
    from veredas.storage import DatabaseManager
    from veredas.storage.repository import InstituicaoRepository, TaxaCDBRepository

    fontes_alvo = list(SCRAPERS.keys()) if fonte == "all" else [fonte]
    invalidas = [f for f in fontes_alvo if f not in SCRAPERS]
    if invalidas:
        rprint(f"[red]✗[/] Corretora(s) desconhecida(s): {', '.join(invalidas)}")
        rprint(f"[dim]Disponíveis: {', '.join(SCRAPERS.keys())}[/]")
        return

    async def _run(col):
        async with col:
            return await col.collect()

    db = DatabaseManager(db_path)
    db.init_db()

    for f in fontes_alvo:
        col = get_collector(f)
        with console.status(f"[bold blue]Coletando {f.upper()}..."):
            result = asyncio.run(_run(col))

        if not result.success:
            rprint(f"  [red]✗[/] {f.upper()}: {result.error}")
            continue

        ofertas = result.data or []
        if not ofertas:
            rprint(f"  [yellow]⚠[/] {f.upper()}: nenhuma oferta encontrada")
            continue

        now = datetime.now(TZ_BRASIL)
        taxas_criadas = 0
        sem_cnpj = 0

        with db.session_scope() as session:
            if_repo = InstituicaoRepository(session)
            taxa_repo = TaxaCDBRepository(session)

            for oferta in ofertas:
                if not oferta.emissor_cnpj:
                    sem_cnpj += 1
                    continue

                if_ = if_repo.upsert(cnpj=oferta.emissor_cnpj, nome=oferta.emissor_nome)
                taxa_repo.create(
                    if_id=if_.id,
                    data_coleta=now,
                    indexador=oferta.indexador,
                    percentual=oferta.percentual,
                    taxa_adicional=oferta.taxa_adicional,
                    prazo_dias=oferta.prazo_dias,
                    valor_minimo=oferta.valor_minimo,
                    liquidez_diaria=oferta.liquidez_diaria,
                    fonte=oferta.fonte,
                    url_fonte=oferta.url_fonte,
                    raw_data=oferta.raw,
                )
                taxas_criadas += 1

        msg = f"  [green]✓[/] {f.upper()}: {taxas_criadas} taxas salvas de {len(ofertas)} ofertas"
        if sem_cnpj:
            msg += f" [dim]({sem_cnpj} sem CNPJ ignoradas)[/]"
        rprint(msg)


def collect_b3(db_path: Path | None, data_str: str | None = None) -> None:
    """Baixa e persiste o Boletim Diário de Renda Fixa Privada da B3."""
    from datetime import date, datetime

    from veredas import TZ_BRASIL
    from veredas.collectors.b3 import B3BoletimCollector
    from veredas.storage import DatabaseManager
    from veredas.storage.models import Indexador
    from veredas.storage.repository import InstituicaoRepository, TaxaCDBRepository

    pregao: date | None = None
    if data_str:
        try:
            pregao = date.fromisoformat(data_str)
        except ValueError:
            rprint(f"[red]✗[/] Data inválida: '{data_str}'. Use o formato YYYY-MM-DD.")
            return

    async def _run(col, d):
        async with col:
            return await col.collect(d)

    col = B3BoletimCollector()
    label = pregao.isoformat() if pregao else "hoje"
    with console.status(f"[bold blue]Baixando Boletim B3 ({label})..."):
        result = asyncio.run(_run(col, pregao))

    if not result.success:
        rprint(f"  [red]✗[/] B3: {result.error}")
        return

    records = result.data or []
    if not records:
        rprint(f"  [yellow]⚠[/] B3: pregão {label} sem dados (feriado ou sem negociações)")
        return

    financeiras = [r for r in records if r.is_financeira]
    rprint(f"  [dim]B3: {len(records)} registros totais, {len(financeiras)} de IFs financeiras[/]")

    if not financeiras:
        rprint("  [yellow]⚠[/] B3: nenhum registro de IF financeira reconhecida — nada persistido")
        return

    db = DatabaseManager(db_path)
    db.init_db()

    now = datetime.now(TZ_BRASIL)
    salvos = 0
    sem_if = 0

    with db.session_scope() as session:
        if_repo = InstituicaoRepository(session)
        taxa_repo = TaxaCDBRepository(session)

        for rec in financeiras:
            cnpj = rec.cnpj_emissor
            if not cnpj:
                sem_if += 1
                continue

            if_ = if_repo.get_by_cnpj(cnpj)
            if if_ is None:
                sem_if += 1
                continue

            taxa_repo.create(
                if_id=if_.id,
                data_coleta=now,
                indexador=Indexador.CDI,
                percentual=rec.taxa_mercado,
                taxa_adicional=None,
                prazo_dias=rec.dias_corridos,
                liquidez_diaria=False,
                fonte="b3",
                mercado="secundario",
                url_fonte=None,
                raw_data={
                    "codigo": rec.codigo,
                    "pu_mercado": str(rec.pu_mercado),
                    "pu_par": str(rec.pu_par),
                    "fator": str(rec.fator_acumulado),
                },
            )
            salvos += 1

    msg = f"  [green]✓[/] B3: {salvos} registros de IFs salvos"
    if sem_if:
        msg += f" [dim]({sem_if} emissores não cadastrados ignorados)[/]"
    rprint(msg)
