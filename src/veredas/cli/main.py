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

# Phase 4 imports
from veredas.collectors.scrapers import (
    SCRAPERS_REGISTRY,
    BaseScraper,
)
from veredas.collectors.b3 import B3MarketDataCollector
from veredas.collectors.alternative import ReclameAquiCollector, BacenProcessosCollector
from veredas.collectors.sentiment import SignalAggregator, NivelRisco

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


# =============================================================================
# Comandos Fase 4 - Scrapers, B3, Dados Alternativos
# =============================================================================


@app.command()
def scrape(
    platform: str = typer.Argument(
        ...,
        help="Plataforma para coletar (xp, btg, rico, nubank, inter, all)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Executa sem salvar no banco",
    ),
):
    """
    Coleta taxas de CDB de plataformas de corretoras.

    Plataformas disponíveis:
    - xp: XP Investimentos
    - btg: BTG Pactual Digital
    - rico: Rico Investimentos
    - nubank: Nubank
    - inter: Banco Inter
    - all: Todas as plataformas
    """
    rprint(f"[bold]Coletando taxas de:[/] {platform}")

    platforms = list(SCRAPERS_REGISTRY.keys()) if platform == "all" else [platform]

    for plat in platforms:
        if plat not in SCRAPERS_REGISTRY:
            rprint(f"[yellow]⚠[/] Plataforma desconhecida: {plat}")
            continue

        scraper_class = SCRAPERS_REGISTRY[plat]

        with console.status(f"[bold blue]Coletando de {plat}..."):
            scraper: BaseScraper = scraper_class()
            result = asyncio.run(scraper.collect())

        if not result.success:
            rprint(f"[red]✗[/] {plat}: {result.error}")
            continue

        data = result.data
        rprint(f"[green]✓[/] {plat}: {len(data.taxas)} taxas coletadas")

        if data.taxas and not dry_run:
            table = Table(title=f"Taxas de {plat}")
            table.add_column("Emissor", style="cyan")
            table.add_column("Taxa", style="green")
            table.add_column("Prazo", style="dim")

            for taxa in data.taxas[:10]:  # Mostra até 10
                table.add_row(
                    taxa.emissor_nome[:30],
                    f"{taxa.percentual}% {taxa.indexador}",
                    f"{taxa.prazo_dias}d",
                )

            if len(data.taxas) > 10:
                table.add_row("...", f"+{len(data.taxas) - 10} taxas", "")

            console.print(table)

    if dry_run:
        rprint("[dim]Modo dry-run: dados não salvos[/]")
    else:
        rprint("\n[green]✓[/] Coleta de plataformas concluída")


@app.command()
def secondary(
    cnpj: Optional[str] = typer.Option(
        None,
        "--cnpj",
        "-c",
        help="CNPJ do emissor para filtrar",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-n",
        help="Número de dias de histórico",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Coleta preços do mercado secundário da B3.

    Busca preços de negociação de CDBs e outros títulos de renda fixa
    no mercado secundário da B3.
    """
    rprint("[bold]Coletando dados do mercado secundário B3...[/]")

    collector = B3MarketDataCollector()

    with console.status("[bold blue]Verificando conexão com B3..."):
        ok = asyncio.run(collector.health_check())

    if not ok:
        rprint("[red]✗[/] B3 Market Data API indisponível")
        rprint("[dim]Verifique sua conexão ou tente novamente mais tarde[/]")
        raise typer.Exit(1)

    with console.status(f"[bold blue]Coletando preços dos últimos {days} dias..."):
        if cnpj:
            precos = asyncio.run(collector.coletar_historico(cnpj, dias=days))
        else:
            precos = asyncio.run(collector.coletar_precos_dia())

    if not precos:
        rprint("[yellow]⚠[/] Nenhum preço encontrado")
        return

    rprint(f"[green]✓[/] {len(precos)} registros de preço coletados")

    table = Table(title="Preços Mercado Secundário")
    table.add_column("Título", style="cyan")
    table.add_column("Emissor", style="dim")
    table.add_column("PU", style="green")
    table.add_column("Variação", style="yellow")

    for preco in precos[:15]:
        var_str = ""
        if preco.variacao_dia:
            var = float(preco.variacao_dia)
            color = "green" if var >= 0 else "red"
            var_str = f"[{color}]{var:+.2f}%[/{color}]"

        table.add_row(
            preco.codigo_titulo[:20],
            preco.emissor_nome[:20] if preco.emissor_nome else preco.emissor_cnpj,
            f"R$ {preco.pu_fechamento:,.4f}",
            var_str,
        )

    if len(precos) > 15:
        table.add_row("...", f"+{len(precos) - 15} registros", "", "")

    console.print(table)


@app.command()
def complaints(
    institution: str = typer.Argument(
        ...,
        help="Nome ou CNPJ da instituição",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Coleta dados de reclamações do Reclame Aqui.

    Busca reputação e métricas de reclamações de instituições financeiras.
    """
    rprint(f"[bold]Buscando reclamações de:[/] {institution}")

    collector = ReclameAquiCollector()

    with console.status("[bold blue]Consultando Reclame Aqui..."):
        reputacao = asyncio.run(collector.buscar_reputacao(institution))

    if not reputacao:
        rprint(f"[yellow]⚠[/] Instituição não encontrada: {institution}")
        return

    # Mostrar reputação
    panel_content = f"""
[bold]Empresa:[/] {reputacao.nome}
[bold]Nota Geral:[/] {reputacao.nota_geral:.1f}/10
[bold]Índice de Solução:[/] {reputacao.indice_solucao:.1f}%
[bold]Índice de Resposta:[/] {reputacao.indice_resposta:.1f}%
[bold]Total de Reclamações:[/] {reputacao.total_reclamacoes:,}
[bold]Reclamações (30d):[/] {reputacao.reclamacoes_ultimos_30d:,}
"""

    # Determinar cor baseada na nota
    border_color = "green" if reputacao.nota_geral >= 7 else "yellow" if reputacao.nota_geral >= 5 else "red"

    console.print(Panel(
        panel_content.strip(),
        title=f"Reputação: {reputacao.classificacao}",
        border_style=border_color,
    ))


@app.command()
def processes(
    cnpj: Optional[str] = typer.Option(
        None,
        "--cnpj",
        "-c",
        help="CNPJ da instituição",
    ),
    active_only: bool = typer.Option(
        True,
        "--active-only/--all",
        help="Mostrar apenas processos ativos",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Consulta processos administrativos do Banco Central.

    Busca processos sancionadores e administrativos contra instituições
    financeiras no histórico do BC.
    """
    rprint("[bold]Consultando processos do Banco Central...[/]")

    collector = BacenProcessosCollector()

    with console.status("[bold blue]Buscando processos..."):
        if cnpj:
            historico = asyncio.run(collector.buscar_por_cnpj(cnpj))
            processos = historico.processos if historico else []
        else:
            # Busca geral (últimos processos)
            processos = asyncio.run(collector.listar_recentes(limit=50))

    if active_only:
        processos = [p for p in processos if p.status.value == "ativo"]

    if not processos:
        rprint("[green]✓[/] Nenhum processo encontrado")
        return

    rprint(f"[yellow]![/] {len(processos)} processo(s) encontrado(s)")

    table = Table(title="Processos BC")
    table.add_column("Número", style="cyan")
    table.add_column("Tipo", style="dim")
    table.add_column("Status", style="yellow")
    table.add_column("Abertura")
    table.add_column("Multa", style="red")

    for proc in processos[:20]:
        multa_str = f"R$ {proc.valor_multa:,.2f}" if proc.valor_multa else "-"
        status_color = "red" if proc.status.value == "ativo" else "dim"

        table.add_row(
            proc.numero,
            proc.tipo.value,
            f"[{status_color}]{proc.status.value}[/{status_color}]",
            str(proc.data_abertura),
            multa_str,
        )

    if len(processos) > 20:
        table.add_row("...", f"+{len(processos) - 20} processos", "", "", "")

    console.print(table)


@app.command()
def risk(
    cnpj: Optional[str] = typer.Option(
        None,
        "--cnpj",
        "-c",
        help="CNPJ da instituição (ou todas se não especificado)",
    ),
    min_level: str = typer.Option(
        "moderado",
        "--min-level",
        "-l",
        help="Nível mínimo de risco (baixo, moderado, elevado, alto, critico)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Caminho para o banco de dados",
    ),
):
    """
    Calcula e exibe sinais de risco agregados.

    Combina sinais de múltiplas fontes (Reclame Aqui, BC, mercado secundário)
    em um score de risco consolidado por instituição.
    """
    rprint("[bold]Calculando sinais de risco agregados...[/]")

    # Mapear níveis
    level_map = {
        "baixo": NivelRisco.BAIXO,
        "moderado": NivelRisco.MODERADO,
        "elevado": NivelRisco.ELEVADO,
        "alto": NivelRisco.ALTO,
        "critico": NivelRisco.CRITICO,
    }

    if min_level.lower() not in level_map:
        rprint(f"[red]✗[/] Nível inválido: {min_level}")
        raise typer.Exit(1)

    min_nivel = level_map[min_level.lower()]

    # Informar sobre implementação
    rprint(Panel(
        "[cyan]ℹ[/] Para análise completa de risco, use a API REST:\n\n"
        "  [bold]POST /api/v1/risk/analyze[/]\n\n"
        "A análise requer dados coletados de:\n"
        "  • Plataformas de corretoras ([bold]veredas scrape all[/])\n"
        "  • Mercado secundário B3 ([bold]veredas secondary[/])\n"
        "  • Reclame Aqui ([bold]veredas complaints[/])\n"
        "  • Processos BC ([bold]veredas processes[/])\n\n"
        f"Filtro: mostrando riscos >= [yellow]{min_level}[/]",
        title="Análise de Risco Agregado",
    ))

    # Verificar se há dados no banco para análise
    db = DatabaseManager(db_path)
    if not db.db_path.exists():
        rprint("\n[yellow]⚠[/] Banco de dados não encontrado. Execute [bold]veredas init[/]")
        return

    rprint("\n[dim]Execute os comandos de coleta para popular o banco antes da análise.[/]")


@app.command()
def sources():
    """
    Lista todas as fontes de dados disponíveis.

    Mostra o status de cada fonte: BCB, scrapers de corretoras,
    B3 mercado secundário, Reclame Aqui e processos do BC.
    """
    rprint("[bold]Fontes de Dados Disponíveis[/]\n")

    # BCB
    rprint("[bold cyan]Banco Central (BCB)[/]")
    rprint("  • Selic, CDI, IPCA")
    rprint("  • Comando: [dim]veredas collect bcb[/]")

    # Scrapers
    rprint("\n[bold cyan]Plataformas de Corretoras (Fase 4)[/]")
    for name, scraper_class in SCRAPERS_REGISTRY.items():
        rprint(f"  • {name}: {scraper_class.__doc__ or 'Scraper de taxas'}")
    rprint("  • Comando: [dim]veredas scrape <plataforma>[/]")

    # B3
    rprint("\n[bold cyan]B3 Mercado Secundário (Fase 4)[/]")
    rprint("  • Preços de CDBs e títulos de renda fixa")
    rprint("  • Comando: [dim]veredas secondary[/]")

    # Dados alternativos
    rprint("\n[bold cyan]Dados Alternativos (Fase 4)[/]")
    rprint("  • Reclame Aqui: reclamações e reputação")
    rprint("  • Comando: [dim]veredas complaints <instituição>[/]")
    rprint("  • Processos BC: sanções e penalidades")
    rprint("  • Comando: [dim]veredas processes[/]")

    # Risco agregado
    rprint("\n[bold cyan]Análise de Risco[/]")
    rprint("  • Score consolidado de múltiplas fontes")
    rprint("  • Comando: [dim]veredas risk[/]")


if __name__ == "__main__":
    app()
