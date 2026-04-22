"""
Sistema de alertas do veredas de papel.

Suporta:
- Console (debug/desenvolvimento)
- Telegram Bot
- Email SMTP
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
from veredas.alerts.manager import AlertManager
from veredas.alerts.telegram import TelegramAlertSender

__all__ = [
    # Base
    "AlertChannel",
    "AlertMessage",
    "AlertPriority",
    "AlertResult",
    "AlertSender",
    "ConsoleSender",
    # Senders
    "TelegramAlertSender",
    "EmailAlertSender",
    # Manager
    "AlertManager",
]
