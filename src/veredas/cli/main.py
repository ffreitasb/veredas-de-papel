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
    if_name: Optional[str] = typer.Option(
        None,
        "--if",
        "-i",
        help="Nome da instituição financeira para analisar",
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

    Analisa as taxas coletadas e detecta comportamentos anômalos.
    """
    rprint("[bold]Executando análise de anomalias...[/]\n")

    # TODO: Implementar análise completa
    # Por enquanto, mostra exemplo

    rprint(Panel(
        "[yellow]⚠ Funcionalidade em desenvolvimento[/]\n\n"
        "A análise completa requer taxas de CDB coletadas.\n"
        "Use [bold]veredas collect[/] primeiro para coletar dados.",
        title="Análise de Anomalias",
    ))

    # Exemplo de como seria a saída
    example_table = Table(title="Exemplo de Anomalias Detectadas")
    example_table.add_column("IF", style="cyan")
    example_table.add_column("Tipo", style="yellow")
    example_table.add_column("Severidade")
    example_table.add_column("Descrição")

    example_table.add_row(
        "Banco Exemplo",
        "SPREAD_CRITICO",
        "[red]CRITICAL[/]",
        "CDB oferecendo 165% do CDI",
    )
    example_table.add_row(
        "Financeira XYZ",
        "SALTO_BRUSCO",
        "[yellow]MEDIUM[/]",
        "Taxa aumentou 15pp em 7 dias",
    )

    console.print(example_table)


@app.command()
def alerts(
    list_all: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Lista todos os alertas ativos",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        "-s",
        help="Filtra por severidade (low, medium, high, critical)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Gerencia alertas de anomalias.

    Lista e filtra alertas ativos no sistema.
    """
    if list_all:
        rprint("[bold]Alertas Ativos[/]\n")

        # TODO: Buscar do banco
        rprint("[dim]Nenhum alerta ativo no momento.[/]")
        rprint("\nUse [bold]veredas analyze[/] para detectar anomalias.")
    else:
        rprint("Use [bold]--list[/] para ver alertas ativos.")


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
