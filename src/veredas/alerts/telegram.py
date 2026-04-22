"""
Sender de alertas via Telegram Bot.

Configuracao via variaveis de ambiente:
- VEREDAS_TELEGRAM_BOT_TOKEN
- VEREDAS_TELEGRAM_CHAT_ID

Para criar um bot:
1. Fale com @BotFather no Telegram
2. Use /newbot e siga as instrucoes
3. Copie o token fornecido

Para obter chat_id:
1. Envie mensagem para seu bot
2. Acesse: https://api.telegram.org/bot<TOKEN>/getUpdates
3. Procure "chat":{"id": XXX}
"""

import logging

import httpx

from veredas.alerts.base import (
    AlertChannel,
    AlertMessage,
    AlertPriority,
    AlertResult,
    AlertSender,
)
from veredas.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramAlertSender(AlertSender):
    """
    Sender de alertas via Telegram Bot API.

    Usa httpx para requisicoes HTTP assincronas.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ):
        """
        Inicializa o sender de Telegram.

        Se parametros nao forem fornecidos, usa config do ambiente.
        """
        settings = get_settings()

        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.TELEGRAM

    @property
    def is_configured(self) -> bool:
        """Verifica se token e chat_id estao configurados."""
        return bool(self.bot_token and self.chat_id)

    def _format_message(self, alert: AlertMessage) -> str:
        """
        Formata mensagem para Telegram.

        Usa Markdown para formatacao.
        """
        # Emoji por prioridade
        emoji = {
            AlertPriority.LOW: "📝",
            AlertPriority.MEDIUM: "⚠️",
            AlertPriority.HIGH: "🔶",
            AlertPriority.CRITICAL: "🚨",
        }.get(alert.prioridade, "📌")

        lines = [
            f"{emoji} *{self._escape_markdown(alert.titulo)}*",
            "",
            self._escape_markdown(alert.corpo),
            "",
            f"⏰ {alert.timestamp.strftime('%d/%m/%Y %H:%M:%S')}",
        ]

        return "\n".join(lines)

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escapa caracteres especiais do Markdown."""
        chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
        for char in chars:
            text = text.replace(char, f"\\{char}")
        return text

    async def send(self, message: AlertMessage) -> AlertResult:
        """
        Envia alerta via Telegram.
        """
        if not self.is_configured:
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Telegram nao configurado. Configure VEREDAS_TELEGRAM_* no ambiente.",
            )

        try:
            url = TELEGRAM_API_URL.format(token=self.bot_token, method="sendMessage")

            payload = {
                "chat_id": self.chat_id,
                "text": self._format_message(message),
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30)
                data = response.json()

            if response.status_code == 200 and data.get("ok"):
                message_id = data.get("result", {}).get("message_id")
                return AlertResult(
                    success=True,
                    channel=self.channel,
                    message_id=str(message_id),
                )
            else:
                error_desc = data.get("description", "Erro desconhecido")
                return AlertResult(
                    success=False,
                    channel=self.channel,
                    error=f"Telegram API: {error_desc}",
                )

        except httpx.TimeoutException:
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Timeout ao conectar com Telegram API",
            )

        except Exception:
            # Log detalhado interno, mensagem generica para usuario
            logger.exception("Falha ao enviar alerta via Telegram")
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Falha ao enviar Telegram. Verifique as configuracoes do bot.",
            )

    async def health_check(self) -> bool:
        """
        Verifica se o bot esta operacional.

        Usa o metodo getMe da API.
        """
        if not self.is_configured:
            return False

        try:
            url = TELEGRAM_API_URL.format(token=self.bot_token, method="getMe")

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()

            return response.status_code == 200 and data.get("ok", False)

        except Exception:
            return False

    async def send_simple(self, text: str) -> AlertResult:
        """
        Envia mensagem simples (sem formatacao).

        Util para testes.
        """
        if not self.is_configured:
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Telegram nao configurado",
            )

        try:
            url = TELEGRAM_API_URL.format(token=self.bot_token, method="sendMessage")

            payload = {
                "chat_id": self.chat_id,
                "text": text,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30)
                data = response.json()

            if response.status_code == 200 and data.get("ok"):
                return AlertResult(
                    success=True,
                    channel=self.channel,
                    message_id=str(data.get("result", {}).get("message_id")),
                )
            else:
                return AlertResult(
                    success=False,
                    channel=self.channel,
                    error=data.get("description", "Erro desconhecido"),
                )

        except Exception:
            logger.exception("Falha ao enviar mensagem simples via Telegram")
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Falha ao enviar mensagem Telegram.",
            )
