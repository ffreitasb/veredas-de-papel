"""
Interface de linha de comando do veredas de papel.

Comandos principais:
- init: Inicializa o banco de dados
- collect: Coleta dados de fontes
- analyze: Executa detecção de anomalias
- alerts: Gerencia alertas
- export: Exporta dados
- status: Mostra status do sistema
- web: Inicia o servidor web
"""

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from veredas import __version__
from veredas.collectors.bcb import BCBCollector, get_cdi_atual, get_selic_atual
from veredas.storage import DatabaseManager, TaxaReferenciaRepository

app = typer.Typer(
    name="veredas",
    help="Monitor de taxas de CDB e detecção de anomalias",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        rprint(f"[bold green]veredas de papel[/] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Mostra a versão e sai",
    ),
):
    """
    veredas de papel - Monitor de taxas de CDB e detecção de anomalias.

    "Nem todo atalho leva ao destino. Monitore o risco."
    """
    pass


@app.command()
def init(
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados SQLite",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Força reinicialização mesmo se já existir",
    ),
):
    """
    Inicializa o banco de dados.

    Cria todas as tabelas necessárias para o funcionamento do sistema.
    """
    try:
        db = DatabaseManager(db_path)
        db_file = db.db_path

        if db_file.exists() and not force:
            rprint(f"[yellow]Banco de dados já existe em:[/] {db_file}")
            rprint("[dim]Use --force para reinicializar[/]")
            return

        db.init_db()
        rprint(f"[green]✓[/] Banco de dados inicializado em: [bold]{db_file}[/]")

    except Exception as e:
        rprint(f"[red]✗[/] Erro ao inicializar banco: {e}")
        raise typer.Exit(1) from e


@app.command()
def collect(
    source: str = typer.Argument(
        "bcb",
        help="Fonte de dados (bcb, ifdata, scrapers, all)",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
    fonte: str = typer.Option(
        "all",
        "--fonte",
        "-f",
        help="Corretora específica para scrapers: xp, btg, inter, rico (padrão: all)",
    ),
    data_b3: str | None = typer.Option(
        None,
        "--data",
        help="Data do pregão B3 em YYYY-MM-DD (padrão: hoje)",
    ),
):
    """
    Coleta dados de fontes externas.

    Fontes disponíveis:
    - bcb:      Taxa Selic, CDI, IPCA do Banco Central
    - ifdata:   Dados de saúde das instituições financeiras
    - scrapers: Prateleiras de CDB das corretoras (XP, BTG, Inter, Rico)
    - b3:       Boletim Diário de Renda Fixa Privada B3 (debêntures secundário)
    - all:      Todas as fontes

    Exemplos:

        veredas collect scrapers --fonte xp

        veredas collect b3

        veredas collect b3 --data 2026-04-23

        veredas collect all
    """
    rprint(f"[bold]Coletando dados de:[/] {source}")

    try:
        if source in ("bcb", "all"):
            _collect_bcb(db_path)

        if source in ("ifdata", "all"):
            _collect_ifdata(db_path)

        if source in ("scrapers", "all"):
            _collect_scrapers(db_path, fonte)

        if source in ("b3", "all"):
            _collect_b3(db_path, data_b3)

        if source not in ("bcb", "ifdata", "scrapers", "b3", "all"):
            rprint(f"[red]✗[/] Fonte desconhecida: '{source}'. Use: bcb, ifdata, scrapers, b3, all")
            raise typer.Exit(1)

        rprint("\n[green]✓[/] Coleta concluída")

    except typer.Exit:
        raise
    except Exception as e:
        rprint(f"[red]✗[/] Erro na coleta: {e}")
        raise typer.Exit(1) from e


def _collect_bcb(db_path: Path | None):
    """Coleta dados do Banco Central."""
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

    # Salvar no banco
    if True:  # Sempre salva no banco padrão
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


def _collect_ifdata(db_path: Path | None):
    """Coleta dados de saúde financeira do IFData e persiste no banco."""
    from veredas.collectors.ifdata import IFDataCollector
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
            # Upsert instituição
            if_ = if_repo.upsert(
                cnpj=dados_if.cnpj,
                nome=dados_if.nome,
                indice_basileia=dados_if.indice_basileia,
                indice_liquidez=dados_if.indice_liquidez,
                ativo_total=dados_if.ativo_total,
                patrimonio_liquido=dados_if.patrimonio_liquido,
            )

            # Persiste snapshot histórico
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


def _collect_scrapers(db_path: Path | None, fonte: str = "all"):
    """Coleta prateleiras de CDB das corretoras e persiste no banco."""
    from datetime import datetime

    from veredas import TZ_BRASIL
    from veredas.collectors.scrapers import SCRAPERS, get_collector
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


def _collect_b3(db_path: Path | None, data_str: str | None = None):
    """Baixa e persiste o Boletim Diário de Renda Fixa Privada da B3."""
    from datetime import date, datetime

    from veredas import TZ_BRASIL
    from veredas.collectors.b3 import B3BoletimCollector
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

            # Upsert da IF pelo CNPJ (nome = prefixo do ticker como fallback)
            if_ = if_repo.get_by_cnpj(cnpj)
            if if_ is None:
                sem_if += 1
                continue

            from veredas.storage.models import Indexador

            # Inferir indexador a partir da taxa (~mercado: DI é CDI)
            indexador = Indexador.CDI

            taxa_repo.create(
                if_id=if_.id,
                data_coleta=now,
                indexador=indexador,
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


@app.command()
def analyze(
    if_id: int | None = typer.Option(
        None,
        "--if-id",
        "-i",
        help="ID da instituição financeira para analisar",
    ),
    days: int = typer.Option(
        30,
        "--days",
        "-n",
        help="Número de dias para análise",
    ),
    enable_ml: bool = typer.Option(
        False,
        "--ml",
        help="Habilitar detectores de Machine Learning",
    ),
    min_severity: str = typer.Option(
        "low",
        "--severity",
        "-s",
        help="Severidade mínima (low, medium, high, critical)",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Executa análise e detecção de anomalias.

    Analisa as taxas coletadas usando detectores de regras,
    estatísticos e opcionalmente de Machine Learning.

    Detectores disponíveis:
    - Regras: spread, variação, divergência
    - Estatísticos: STL decomposition, change point, rolling z-score
    - ML: Isolation Forest, DBSCAN (requer --ml)
    """
    from veredas.detectors import DetectionEngine, EngineConfig
    from veredas.storage.models import Severidade

    rprint("[bold]Executando análise de anomalias...[/]\n")

    # Mapear severidade
    severity_map = {
        "low": Severidade.LOW,
        "medium": Severidade.MEDIUM,
        "high": Severidade.HIGH,
        "critical": Severidade.CRITICAL,
    }

    if min_severity.lower() not in severity_map:
        rprint(f"[red]✗[/] Severidade inválida: {min_severity}")
        raise typer.Exit(1)

    # Configurar engine
    config = EngineConfig(
        enable_rules=True,
        enable_statistical=True,
        enable_ml=enable_ml,
        min_severity=severity_map[min_severity.lower()],
        deduplicate=True,
    )

    engine = DetectionEngine(config)

    # Mostrar detectores disponíveis
    rprint("[bold]Detectores habilitados:[/]")
    rprint("  • Regras: [green]✓[/]")
    rprint("  • Estatísticos: [green]✓[/]")
    rprint(f"  • Machine Learning: {'[green]✓[/]' if enable_ml else '[dim]✗[/]'}")
    rprint()

    # Verificar se há dados no banco
    db = DatabaseManager(db_path)
    if not db.db_path.exists():
        rprint(
            Panel(
                "[yellow]⚠ Banco de dados não encontrado[/]\n\n"
                "Execute [bold]veredas init[/] para criar o banco.\n"
                "Use [bold]veredas collect[/] para coletar taxas.",
                title="Dados Necessários",
            )
        )
        raise typer.Exit(1)

    # Por enquanto, mostra exemplo (banco pode não ter taxas CDB)
    rprint(
        Panel(
            "[cyan]ℹ[/] Para análise completa, é necessário ter taxas de CDB no banco.\n\n"
            "Use a [bold]API REST[/] para analisar dados:\n"
            "  [dim]POST /api/v1/detection/analyze[/]\n\n"
            "Ou inicie o servidor web:\n"
            "  [bold]veredas web[/]",
            title="Análise de Anomalias",
        )
    )

    # Mostrar detectores disponíveis
    detectors = engine.available_detectors()
    detector_table = Table(title="Detectores Disponíveis")
    detector_table.add_column("Categoria", style="cyan")
    detector_table.add_column("Detectores")

    for category, names in detectors.items():
        detector_table.add_row(category.value.title(), ", ".join(names))

    console.print(detector_table)


alerts_app = typer.Typer(name="alerts", help="Gerencia canais de alerta", no_args_is_help=True)
app.add_typer(alerts_app)


@alerts_app.command("status")
def alerts_status():
    """Mostra canais de alerta configurados e seu estado."""
    from veredas.alerts import AlertChannel, AlertManager

    manager = AlertManager()
    channels = manager.channels_configured

    table = Table(title="Canais de Alerta")
    table.add_column("Canal", style="cyan")
    table.add_column("Estado")

    all_channels = [AlertChannel.TELEGRAM, AlertChannel.EMAIL]
    for ch in all_channels:
        if ch in channels:
            table.add_row(ch.value, "[green]✓ Configurado[/]")
        else:
            table.add_row(ch.value, "[dim]✗ Não configurado[/]")

    console.print(table)

    if not channels:
        rprint(
            "\n[yellow]⚠[/] Nenhum canal configurado. Defina as variáveis de ambiente:\n"
            "  [dim]VEREDAS_TELEGRAM_BOT_TOKEN / VEREDAS_TELEGRAM_CHAT_ID[/]\n"
            "  [dim]VEREDAS_SMTP_HOST / VEREDAS_SMTP_USER / VEREDAS_SMTP_PASSWORD / VEREDAS_ALERT_EMAIL_TO[/]"
        )


@alerts_app.command("test")
def alerts_test(
    channel: str | None = typer.Option(
        None,
        "--channel",
        "-c",
        help="Canal específico: telegram, email (padrão: todos)",
    ),
):
    """Envia alerta de teste para canal(is) configurado(s)."""
    from veredas.alerts import AlertChannel, AlertManager

    manager = AlertManager()

    if not manager.senders:
        rprint(
            "[red]✗[/] Nenhum canal configurado. Use [bold]veredas alerts status[/] para detalhes."
        )
        raise typer.Exit(1)

    target: AlertChannel | None = None
    if channel:
        try:
            target = AlertChannel(channel.lower())
        except ValueError:
            rprint(f"[red]✗[/] Canal inválido: {channel}. Use: telegram, email")
            raise typer.Exit(1) from None

    rprint("[bold]Enviando alerta de teste...[/]")
    results = asyncio.run(manager.send_test_alert(target))

    for result in results:
        if result.success:
            rprint(f"  [green]✓[/] {result.channel.value}: enviado (id={result.message_id})")
        else:
            rprint(f"  [red]✗[/] {result.channel.value}: {result.error}")


@app.command()
def export(
    tipo: str = typer.Argument(
        "anomalias",
        help="O que exportar: anomalias, taxas, all",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Formato de exportação: csv, json",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Arquivo de saída (padrão: veredas_<tipo>_<timestamp>.<format>)",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
    todas: bool = typer.Option(
        False,
        "--todas",
        help="Incluir anomalias já resolvidas (padrão: apenas ativas)",
    ),
):
    """
    Exporta dados coletados para CSV ou JSON.

    Exemplos:

        veredas export anomalias

        veredas export taxas --format json

        veredas export all --output backup.csv --todas
    """
    if tipo not in ("anomalias", "taxas", "all"):
        rprint(f"[red]✗[/] Tipo inválido: '{tipo}'. Use: anomalias, taxas, all")
        raise typer.Exit(1) from None

    if format not in ("csv", "json"):
        rprint(f"[red]✗[/] Formato inválido: '{format}'. Use: csv, json")
        raise typer.Exit(1) from None

    from veredas.storage import AnomaliaRepository, TaxaCDBRepository

    try:
        db = DatabaseManager(db_path)
        with db.session_scope() as session:
            if tipo in ("anomalias", "all"):
                filters = {} if todas else {"resolvido": False}
                anomalias = AnomaliaRepository(session).list_with_filters(
                    filters=filters, limit=50_000, eager_load=True
                )
                dest = output or Path(f"veredas_anomalias_{datetime.now():%Y%m%d_%H%M%S}.{format}")
                _exportar_anomalias(list(anomalias), format, dest)
                rprint(f"[green]✓[/] {len(anomalias)} anomalias → [bold]{dest}[/]")

            if tipo in ("taxas", "all"):
                taxas, _ = TaxaCDBRepository(session).list_paginated(page=1, per_page=50_000)
                if tipo == "all":
                    stem = (
                        dest.stem.replace("anomalias", "taxas")
                        if output
                        else f"veredas_taxas_{datetime.now():%Y%m%d_%H%M%S}"
                    )
                    dest_taxas = Path(f"{stem}.{format}")
                else:
                    dest_taxas = output or Path(
                        f"veredas_taxas_{datetime.now():%Y%m%d_%H%M%S}.{format}"
                    )
                _exportar_taxas(list(taxas), format, dest_taxas)
                rprint(f"[green]✓[/] {len(taxas)} taxas → [bold]{dest_taxas}[/]")

    except Exception as e:
        rprint(f"[red]✗[/] Erro na exportação: {e}")
        raise typer.Exit(1) from e


def _exportar_anomalias(anomalias: list, format: str, dest: Path) -> None:
    if format == "csv":
        with dest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
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
            for a in anomalias:
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
    else:
        rows = [
            {
                "id": a.id,
                "tipo": a.tipo.value,
                "severidade": a.severidade.value,
                "instituicao": a.instituicao.nome if a.instituicao else None,
                "cnpj": a.instituicao.cnpj if a.instituicao else None,
                "valor_detectado": float(a.valor_detectado)
                if a.valor_detectado is not None
                else None,
                "valor_esperado": float(a.valor_esperado) if a.valor_esperado is not None else None,
                "desvio": float(a.desvio) if a.desvio is not None else None,
                "descricao": a.descricao,
                "detectado_em": a.detectado_em.isoformat() if a.detectado_em else None,
                "resolvido": a.resolvido,
                "resolvido_em": a.resolvido_em.isoformat() if a.resolvido_em else None,
            }
            for a in anomalias
        ]
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _exportar_taxas(taxas: list, format: str, dest: Path) -> None:
    if format == "csv":
        with dest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                [
                    "Data Coleta",
                    "Instituição",
                    "CNPJ",
                    "Indexador",
                    "Percentual (%)",
                    "Taxa Adicional (%)",
                    "Prazo (dias)",
                    "Liquidez Diária",
                    "Fonte",
                    "Mercado",
                    "Risk Score",
                ]
            )
            for t in taxas:
                writer.writerow(
                    [
                        t.data_coleta.strftime("%d/%m/%Y"),
                        t.instituicao.nome if t.instituicao else "",
                        t.instituicao.cnpj if t.instituicao else "",
                        t.indexador.value,
                        str(t.percentual).replace(".", ","),
                        str(t.taxa_adicional).replace(".", ",") if t.taxa_adicional else "",
                        t.prazo_dias,
                        "Sim" if t.liquidez_diaria else "Não",
                        t.fonte,
                        t.mercado or "",
                        str(t.risk_score).replace(".", ",") if t.risk_score else "",
                    ]
                )
    else:
        rows = [
            {
                "id": t.id,
                "data_coleta": t.data_coleta.isoformat(),
                "instituicao": t.instituicao.nome if t.instituicao else None,
                "cnpj": t.instituicao.cnpj if t.instituicao else None,
                "indexador": t.indexador.value,
                "percentual": float(t.percentual),
                "taxa_adicional": float(t.taxa_adicional) if t.taxa_adicional else None,
                "prazo_dias": t.prazo_dias,
                "liquidez_diaria": t.liquidez_diaria,
                "fonte": t.fonte,
                "mercado": t.mercado,
                "risk_score": float(t.risk_score) if t.risk_score else None,
            }
            for t in taxas
        ]
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


@app.command()
def detectors():
    """
    Lista detectores de anomalias disponíveis.

    Mostra todos os detectores por categoria: regras, estatísticos e ML.
    """
    from veredas.detectors import DetectionEngine

    rprint("[bold]Detectores de Anomalias Disponíveis[/]\n")

    detectors = DetectionEngine.available_detectors()

    # Verificar dependências ML
    ml_available = False
    ruptures_available = False

    try:
        import sklearn  # noqa: F401

        ml_available = True
    except ImportError:
        pass

    try:
        import ruptures  # noqa: F401

        ruptures_available = True
    except ImportError:
        pass

    # Regras
    rprint("[bold cyan]Detectores de Regras:[/]")
    for name in detectors.get("rules", []):
        rprint(f"  • {name}")

    # Estatísticos
    rprint("\n[bold cyan]Detectores Estatísticos:[/]")
    for name in detectors.get("statistical", []):
        status = "[green]✓[/]"
        if "change_point" in name and not ruptures_available:
            status = "[yellow]⚠ ruptures não instalado[/]"
        rprint(f"  • {name} {status}")

    # ML
    rprint("\n[bold cyan]Detectores de Machine Learning:[/]")
    for name in detectors.get("ml", []):
        status = "[green]✓[/]" if ml_available else "[yellow]⚠ scikit-learn não instalado[/]"
        rprint(f"  • {name} {status}")

    rprint("\n[dim]Use --ml com 'veredas analyze' para habilitar detectores ML[/]")


@app.command()
def web(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host para bind do servidor",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Porta para bind do servidor",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Habilita hot reload (desenvolvimento)",
    ),
):
    """
    Inicia o servidor web.

    Executa a interface web do veredas de papel.
    Acesse http://localhost:8000 após iniciar.
    """
    rprint("[bold]Iniciando servidor web...[/]")
    rprint(f"  Host: [cyan]{host}[/]")
    rprint(f"  Porta: [cyan]{port}[/]")
    rprint(f"  Reload: [cyan]{reload}[/]")
    rprint(f"\n[green]Acesse:[/] [bold]http://{host}:{port}[/]\n")

    try:
        from veredas.web.app import run_server

        run_server(host=host, port=port, reload=reload)
    except ImportError as e:
        rprint(f"[red]✗[/] Dependencias web nao instaladas: {e}")
        rprint("  Instale com: [bold]pip install veredas-de-papel[web][/]")
        raise typer.Exit(1) from e
    except Exception as e:
        rprint(f"[red]✗[/] Erro ao iniciar servidor: {e}")
        raise typer.Exit(1) from e


@app.command()
def status(
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Mostra status do sistema.

    Exibe informações sobre dados coletados, última atualização, etc.
    """
    rprint(
        Panel.fit(
            f"[bold green]veredas de papel[/] v{__version__}\n"
            "[dim]Monitor de taxas de CDB e detecção de anomalias[/]",
            border_style="green",
        )
    )

    rprint("\n[bold]Status das Fontes:[/]")

    # Verificar BCB
    with console.status("Verificando BCB..."):
        collector = BCBCollector()
        bcb_ok = asyncio.run(collector.health_check())

    if bcb_ok:
        rprint("  [green]✓[/] Banco Central (BCB): Online")
    else:
        rprint("  [red]✗[/] Banco Central (BCB): Offline")

    # Mostrar últimas taxas
    rprint("\n[bold]Taxas Atuais:[/]")

    selic = get_selic_atual()
    cdi = get_cdi_atual()

    if selic:
        rprint(f"  • Selic: [green]{selic}%[/] a.m.")
    if cdi:
        rprint(f"  • CDI: [green]{cdi}%[/] a.m.")

    # Status do banco
    db = DatabaseManager(db_path)
    if db.db_path.exists():
        rprint(f"\n[bold]Banco de Dados:[/] {db.db_path}")
        rprint(f"  • Tamanho: {db.db_path.stat().st_size / 1024:.1f} KB")
    else:
        rprint("\n[yellow]⚠[/] Banco de dados não inicializado. Use [bold]veredas init[/]")


if __name__ == "__main__":
    app()
