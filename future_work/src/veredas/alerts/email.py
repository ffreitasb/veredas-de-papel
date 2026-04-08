"""
Sender de alertas via email (SMTP).

Configuracao via variaveis de ambiente:
- VEREDAS_SMTP_HOST
- VEREDAS_SMTP_PORT
- VEREDAS_SMTP_USER
- VEREDAS_SMTP_PASSWORD
- VEREDAS_ALERT_EMAIL_TO
- VEREDAS_ALERT_EMAIL_FROM
"""

import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

from veredas.alerts.base import (
    AlertChannel,
    AlertMessage,
    AlertResult,
    AlertSender,
)
from veredas.config import get_settings


class EmailAlertSender(AlertSender):
    """
    Sender de alertas via email SMTP.

    Suporta TLS e autenticacao.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        email_to: Optional[str] = None,
        email_from: Optional[str] = None,
    ):
        """
        Inicializa o sender de email.

        Se parametros nao forem fornecidos, usa config do ambiente.
        """
        settings = get_settings()

        self.smtp_host = smtp_host or settings.smtp_host
        self.smtp_port = smtp_port or settings.smtp_port
        self.smtp_user = smtp_user or settings.smtp_user
        self.smtp_password = smtp_password or settings.smtp_password
        self.email_to = email_to or settings.alert_email_to
        self.email_from = email_from or settings.smtp_user

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.EMAIL

    @property
    def is_configured(self) -> bool:
        """Verifica se todas as configs necessarias estao presentes."""
        return all([
            self.smtp_host,
            self.smtp_port,
            self.smtp_user,
            self.smtp_password,
            self.email_to,
        ])

    def _criar_mensagem(self, alert: AlertMessage) -> MIMEMultipart:
        """Cria mensagem MIME para envio."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[veredas] {alert.titulo}"
        msg["From"] = self.email_from or self.smtp_user
        msg["To"] = self.email_to

        # Corpo texto
        text_body = f"""
veredas de papel - Alerta de Anomalia
=====================================

{alert.corpo}

---
Prioridade: {alert.prioridade.value.upper()}
Timestamp: {alert.timestamp}
"""

        # Corpo HTML
        prioridade_cor = {
            "low": "#28a745",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545",
        }.get(alert.prioridade.value, "#6c757d")

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .header {{ background: #1a1a2e; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .priority {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 4px;
            background: {prioridade_cor};
            color: white;
            font-weight: bold;
        }}
        .footer {{ padding: 10px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>veredas de papel</h1>
        <p>Monitor de taxas de CDB</p>
    </div>
    <div class="content">
        <h2>{alert.titulo}</h2>
        <p class="priority">{alert.prioridade.value.upper()}</p>
        <pre>{alert.corpo}</pre>
    </div>
    <div class="footer">
        <p>Timestamp: {alert.timestamp}</p>
        <p><em>"Nem todo atalho leva ao destino. Monitore o risco."</em></p>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return msg

    async def send(self, message: AlertMessage) -> AlertResult:
        """
        Envia alerta via email.

        Usa aiosmtplib para envio assincrono.
        """
        if not self.is_configured:
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Email nao configurado. Configure VEREDAS_SMTP_* no ambiente.",
            )

        try:
            import aiosmtplib

            msg = self._criar_mensagem(message)

            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )

            return AlertResult(
                success=True,
                channel=self.channel,
                message_id=f"email_{message.timestamp.timestamp()}",
            )

        except ImportError:
            return AlertResult(
                success=False,
                channel=self.channel,
                error="aiosmtplib nao instalado. Instale com: pip install aiosmtplib",
            )

        except Exception as e:
            # Log detalhado interno, mensagem generica para usuario
            logger.exception("Falha ao enviar email de alerta")
            return AlertResult(
                success=False,
                channel=self.channel,
                error="Falha ao enviar email. Verifique as configuracoes SMTP.",
            )

    async def health_check(self) -> bool:
        """
        Verifica conectividade com servidor SMTP.
        """
        if not self.is_configured:
            return False

        try:
            import aiosmtplib

            # Apenas tenta conectar
            smtp = aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
            )
            await asyncio.wait_for(smtp.connect(), timeout=10)
            await smtp.quit()
            return True

        except Exception:
            return False
