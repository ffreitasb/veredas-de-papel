"""
Sistema de alertas do veredas de papel.

Suporta:
- Console (debug/desenvolvimento)
"""

from veredas.alerts.base import (
    AlertChannel,
    AlertMessage,
    AlertPriority,
    AlertResult,
    AlertSender,
    ConsoleSender,
)

__all__ = [
    # Base
    "AlertChannel",
    "AlertMessage",
    "AlertPriority",
    "AlertResult",
    "AlertSender",
    "ConsoleSender",
]
