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
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    db_path: Optional[Path] = typer.Option(
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
        raise typer.Exit(1)


@app.command()
def collect(
    source: str = typer.Argument(
        "bcb",
        help="Fonte de dados (bcb, ifdata, all)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Coleta dados de fontes externas.

    Fontes disponíveis:
    - bcb: Taxa Selic, CDI, IPCA do Banco Central
    - ifdata: Dados de saúde das instituições financeiras
    - all: Todas as fontes
    """
    rprint(f"[bold]Coletando dados de:[/] {source}")

    try:
        if source in ("bcb", "all"):
            _collect_bcb(db_path)

        if source in ("ifdata", "all"):
            rprint("[yellow]⚠[/] Coletor IFData ainda não implementado")

        rprint("\n[green]✓[/] Coleta concluída")

    except Exception as e:
        rprint(f"[red]✗[/] Erro na coleta: {e}")
        raise typer.Exit(1)


def _collect_bcb(db_path: Optional[Path]):
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
    if db_path or True:  # Sempre salva no banco padrão
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


@app.command()
def analyze(
    if_id: Optional[int] = typer.Option(
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
    db_path: Optional[Path] = typer.Option(
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
    rprint(f"  • Regras: [green]✓[/]")
    rprint(f"  • Estatísticos: [green]✓[/]")
    rprint(f"  • Machine Learning: {'[green]✓[/]' if enable_ml else '[dim]✗[/]'}")
    rprint()

    # Verificar se há dados no banco
    db = DatabaseManager(db_path)
    if not db.db_path.exists():
        rprint(Panel(
            "[yellow]⚠ Banco de dados não encontrado[/]\n\n"
            "Execute [bold]veredas init[/] para criar o banco.\n"
            "Use [bold]veredas collect[/] para coletar taxas.",
            title="Dados Necessários",
        ))
        raise typer.Exit(1)

    # Por enquanto, mostra exemplo (banco pode não ter taxas CDB)
    rprint(Panel(
        "[cyan]ℹ[/] Para análise completa, é necessário ter taxas de CDB no banco.\n\n"
        "Use a [bold]API REST[/] para analisar dados:\n"
        "  [dim]POST /api/v1/detection/analyze[/]\n\n"
        "Ou inicie o servidor web:\n"
        "  [bold]veredas web[/]",
        title="Análise de Anomalias",
    ))

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
    from veredas.alerts import AlertManager, AlertChannel

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
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        "-c",
        help="Canal específico: telegram, email (padrão: todos)",
    ),
):
    """Envia alerta de teste para canal(is) configurado(s)."""
    from veredas.alerts import AlertManager, AlertChannel

    manager = AlertManager()

    if not manager.senders:
        rprint("[red]✗[/] Nenhum canal configurado. Use [bold]veredas alerts status[/] para detalhes.")
        raise typer.Exit(1)

    target: Optional[AlertChannel] = None
    if channel:
        try:
            target = AlertChannel(channel.lower())
        except ValueError:
            rprint(f"[red]✗[/] Canal inválido: {channel}. Use: telegram, email")
            raise typer.Exit(1)

    rprint("[bold]Enviando alerta de teste...[/]")
    results = asyncio.run(manager.send_test_alert(target))

    for result in results:
        if result.success:
            rprint(f"  [green]✓[/] {result.channel.value}: enviado (id={result.message_id})")
        else:
            rprint(f"  [red]✗[/] {result.channel.value}: {result.error}")


@app.command()
def export(
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Formato de exportação (csv, json)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Arquivo de saída",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Exporta dados coletados.

    Formatos suportados: CSV, JSON
    """
    if output is None:
        output = Path(f"veredas_export_{datetime.now():%Y%m%d_%H%M%S}.{format}")

    rprint(f"[bold]Exportando dados para:[/] {output}")

    # TODO: Implementar exportação
    rprint(Panel(
        "[yellow]⚠ Funcionalidade em desenvolvimento[/]",
        title="Exportação",
    ))


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
    rprint(f"[bold]Iniciando servidor web...[/]")
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
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/] Erro ao iniciar servidor: {e}")
        raise typer.Exit(1)


@app.command()
def status(
    db_path: Optional[Path] = typer.Option(
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
    rprint(Panel.fit(
        f"[bold green]veredas de papel[/] v{__version__}\n"
        "[dim]Monitor de taxas de CDB e detecção de anomalias[/]",
        border_style="green",
    ))

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
