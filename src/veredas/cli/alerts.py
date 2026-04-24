"""Sub-app Typer para comandos de alerta."""

import asyncio

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

alerts_app = typer.Typer(name="alerts", help="Gerencia canais de alerta", no_args_is_help=True)

console = Console()


@alerts_app.command("status")
def alerts_status() -> None:
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
            "  [dim]VEREDAS_SMTP_HOST / VEREDAS_SMTP_USER / VEREDAS_SMTP_PASSWORD"
            " / VEREDAS_ALERT_EMAIL_TO[/]"
        )


@alerts_app.command("test")
def alerts_test(
    channel: str | None = typer.Option(
        None,
        "--channel",
        "-c",
        help="Canal específico: telegram, email (padrão: todos)",
    ),
) -> None:
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
