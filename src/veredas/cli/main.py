"""
Interface de linha de comando do veredas de papel.

Comandos principais:
- init: Inicializa o banco de dados
- collect: Coleta dados de fontes
- analyze: Executa detecção de anomalias
- alerts: Gerencia alertas
- export: Exporta dados
- detectors: Lista detectores disponíveis
- status: Mostra status do sistema
- web: Inicia o servidor web
"""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from veredas import TZ_BRASIL, __version__
from veredas.cli._collect import collect_b3, collect_bcb, collect_ifdata, collect_scrapers
from veredas.cli._export import exportar_anomalias, exportar_taxas
from veredas.cli.alerts import alerts_app
from veredas.collectors.bcb import BCBCollector, get_cdi_atual, get_selic_atual
from veredas.storage import DatabaseManager

app = typer.Typer(
    name="veredas",
    help="Monitor de taxas de CDB e detecção de anomalias",
    add_completion=False,
    no_args_is_help=True,
)
app.add_typer(alerts_app)

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
        help="Fonte de dados (bcb, ifdata, scrapers, b3, all)",
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
            collect_bcb(db_path)

        if source in ("ifdata", "all"):
            collect_ifdata(db_path)

        if source in ("scrapers", "all"):
            collect_scrapers(db_path, fonte)

        if source in ("b3", "all"):
            collect_b3(db_path, data_b3)

        if source not in ("bcb", "ifdata", "scrapers", "b3", "all"):
            rprint(f"[red]✗[/] Fonte desconhecida: '{source}'. Use: bcb, ifdata, scrapers, b3, all")
            raise typer.Exit(1)

        rprint("\n[green]✓[/] Coleta concluída")

    except typer.Exit:
        raise
    except Exception as e:
        rprint(f"[red]✗[/] Erro na coleta: {e}")
        raise typer.Exit(1) from e


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
    """
    from veredas.detectors import DetectionEngine, EngineConfig
    from veredas.storage.models import Severidade

    rprint("[bold]Executando análise de anomalias...[/]\n")

    severity_map = {
        "low": Severidade.LOW,
        "medium": Severidade.MEDIUM,
        "high": Severidade.HIGH,
        "critical": Severidade.CRITICAL,
    }

    if min_severity.lower() not in severity_map:
        rprint(f"[red]✗[/] Severidade inválida: {min_severity}")
        raise typer.Exit(1)

    config = EngineConfig(
        enable_rules=True,
        enable_statistical=True,
        enable_ml=enable_ml,
        min_severity=severity_map[min_severity.lower()],
        deduplicate=True,
    )
    engine = DetectionEngine(config)

    rprint("[bold]Detectores habilitados:[/]")
    rprint("  • Regras: [green]✓[/]")
    rprint("  • Estatísticos: [green]✓[/]")
    rprint(f"  • Machine Learning: {'[green]✓[/]' if enable_ml else '[dim]✗[/]'}")
    rprint()

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

    detectors = engine.available_detectors()
    detector_table = Table(title="Detectores Disponíveis")
    detector_table.add_column("Categoria", style="cyan")
    detector_table.add_column("Detectores")
    for category, names in detectors.items():
        detector_table.add_row(category.value.title(), ", ".join(names))
    console.print(detector_table)


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
                dest = output or Path(
                    f"veredas_anomalias_{datetime.now(TZ_BRASIL):%Y%m%d_%H%M%S}.{format}"
                )
                exportar_anomalias(list(anomalias), format, dest)
                rprint(f"[green]✓[/] {len(anomalias)} anomalias → [bold]{dest}[/]")

            if tipo in ("taxas", "all"):
                taxas, _ = TaxaCDBRepository(session).list_paginated(page=1, per_page=50_000)
                if tipo == "all":
                    stem = (
                        dest.stem.replace("anomalias", "taxas")
                        if output
                        else f"veredas_taxas_{datetime.now(TZ_BRASIL):%Y%m%d_%H%M%S}"
                    )
                    dest_taxas = Path(f"{stem}.{format}")
                else:
                    dest_taxas = output or Path(
                        f"veredas_taxas_{datetime.now(TZ_BRASIL):%Y%m%d_%H%M%S}.{format}"
                    )
                exportar_taxas(list(taxas), format, dest_taxas)
                rprint(f"[green]✓[/] {len(taxas)} taxas → [bold]{dest_taxas}[/]")

    except Exception as e:
        rprint(f"[red]✗[/] Erro na exportação: {e}")
        raise typer.Exit(1) from e


@app.command()
def detectors():
    """
    Lista detectores de anomalias disponíveis.

    Mostra todos os detectores por categoria: regras, estatísticos e ML.
    """
    from veredas.detectors import DetectionEngine

    rprint("[bold]Detectores de Anomalias Disponíveis[/]\n")

    available = DetectionEngine.available_detectors()

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

    rprint("[bold cyan]Detectores de Regras:[/]")
    for name in available.get("rules", []):
        rprint(f"  • {name}")

    rprint("\n[bold cyan]Detectores Estatísticos:[/]")
    for name in available.get("statistical", []):
        status_str = "[green]✓[/]"
        if "change_point" in name and not ruptures_available:
            status_str = "[yellow]⚠ ruptures não instalado[/]"
        rprint(f"  • {name} {status_str}")

    rprint("\n[bold cyan]Detectores de Machine Learning:[/]")
    for name in available.get("ml", []):
        status_str = "[green]✓[/]" if ml_available else "[yellow]⚠ scikit-learn não instalado[/]"
        rprint(f"  • {name} {status_str}")

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

    with console.status("Verificando BCB..."):
        collector = BCBCollector()
        bcb_ok = asyncio.run(collector.health_check())

    if bcb_ok:
        rprint("  [green]✓[/] Banco Central (BCB): Online")
    else:
        rprint("  [red]✗[/] Banco Central (BCB): Offline")

    rprint("\n[bold]Taxas Atuais:[/]")
    selic = get_selic_atual()
    cdi = get_cdi_atual()
    if selic:
        rprint(f"  • Selic: [green]{selic}%[/] a.m.")
    if cdi:
        rprint(f"  • CDI: [green]{cdi}%[/] a.m.")

    db = DatabaseManager(db_path)
    if db.db_path.exists():
        rprint(f"\n[bold]Banco de Dados:[/] {db.db_path}")
        rprint(f"  • Tamanho: {db.db_path.stat().st_size / 1024:.1f} KB")
    else:
        rprint("\n[yellow]⚠[/] Banco de dados não inicializado. Use [bold]veredas init[/]")


if __name__ == "__main__":
    app()
