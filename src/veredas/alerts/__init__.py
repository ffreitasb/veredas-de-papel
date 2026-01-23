"""
Sistema de alertas do veredas de papel.

Suporta multiplos canais:
- Email (SMTP)
- Telegram (Bot API)
- Console (debug)
"""

from veredas.alerts.base import (
    AlertChannel,
    AlertMessage,
    AlertPriority,
    AlertResult,
    AlertSender,
    ConsoleSender,
)
from veredas.alerts.email import EmailAlertSender
from veredas.alerts.telegram import TelegramAlertSender
from veredas.alerts.manager import AlertManager

__all__ = [
    # Base
    "AlertChannel",
    "AlertMessage",
    "AlertPriority",
    "AlertResult",
    "AlertSender",
    "ConsoleSender",
    # Senders
    "EmailAlertSender",
    "TelegramAlertSender",
    # Manager
    "AlertManager",
]
