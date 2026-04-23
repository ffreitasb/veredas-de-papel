"""
Interface base para senders de alertas.

Define o contrato que todos os canais de alerta devem implementar.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from veredas.storage.models import Anomalia

logger = logging.getLogger(__name__)


class AlertChannel(StrEnum):
    """Canais de alerta disponiveis."""

    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class AlertPriority(StrEnum):
    """Prioridade do alerta."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_severity(cls, severity: str) -> "AlertPriority":
        """Converte severidade de anomalia para prioridade."""
        mapping = {
            "LOW": cls.LOW,
            "MEDIUM": cls.MEDIUM,
            "HIGH": cls.HIGH,
            "CRITICAL": cls.CRITICAL,
        }
        return mapping.get(severity.upper(), cls.MEDIUM)


@dataclass
class AlertMessage:
    """Mensagem de alerta formatada."""

    titulo: str
    corpo: str
    prioridade: AlertPriority
    anomalia_id: int | None = None
    if_nome: str | None = None
    tipo_anomalia: str | None = None
    valor_detectado: str | None = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @classmethod
    def from_anomalia(cls, anomalia: Anomalia) -> "AlertMessage":
        """Cria mensagem a partir de uma anomalia."""
        prioridade = AlertPriority.from_severity(anomalia.severidade)

        titulo = f"[{anomalia.severidade}] {anomalia.tipo}"
        corpo = cls._formatar_corpo(anomalia)

        return cls(
            titulo=titulo,
            corpo=corpo,
            prioridade=prioridade,
            anomalia_id=anomalia.id,
            if_nome=anomalia.instituicao.nome if anomalia.instituicao else None,
            tipo_anomalia=anomalia.tipo,
            valor_detectado=str(anomalia.valor_detectado),
        )

    @staticmethod
    def _formatar_corpo(anomalia: Anomalia) -> str:
        """Formata corpo da mensagem."""
        linhas = [
            f"Anomalia detectada: {anomalia.tipo}",
            f"Severidade: {anomalia.severidade}",
        ]

        if anomalia.instituicao:
            linhas.append(f"Instituicao: {anomalia.instituicao.nome}")

        if anomalia.valor_detectado:
            linhas.append(f"Valor: {anomalia.valor_detectado}")

        if anomalia.valor_esperado:
            linhas.append(f"Esperado: {anomalia.valor_esperado}")

        if anomalia.desvio:
            linhas.append(f"Desvio: {anomalia.desvio}")

        if anomalia.detalhes:
            linhas.append(f"Detalhes: {anomalia.detalhes}")

        return "\n".join(linhas)


@dataclass
class AlertResult:
    """Resultado do envio de alerta."""

    success: bool
    channel: AlertChannel
    message_id: str | None = None
    error: str | None = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AlertSender(ABC):
    """
    Interface base para senders de alertas.

    Todos os canais de alerta devem implementar esta interface.
    """

    @property
    @abstractmethod
    def channel(self) -> AlertChannel:
        """Retorna o tipo de canal."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Verifica se o canal esta configurado corretamente."""
        ...

    @abstractmethod
    async def send(self, message: AlertMessage) -> AlertResult:
        """
        Envia uma mensagem de alerta.

        Args:
            message: Mensagem a enviar.

        Returns:
            AlertResult com status do envio.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifica se o canal esta operacional.

        Returns:
            True se operacional, False caso contrario.
        """
        ...

    async def send_anomalia(self, anomalia: Anomalia) -> AlertResult:
        """
        Envia alerta para uma anomalia.

        Conveniencia que cria AlertMessage automaticamente.

        Args:
            anomalia: Anomalia a alertar.

        Returns:
            AlertResult com status do envio.
        """
        message = AlertMessage.from_anomalia(anomalia)
        return await self.send(message)


class ConsoleSender(AlertSender):
    """
    Sender de alertas para console.

    Util para desenvolvimento e testes.
    """

    @property
    def channel(self) -> AlertChannel:
        return AlertChannel.CONSOLE

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, message: AlertMessage) -> AlertResult:
        """Imprime alerta no console via logging."""
        log_message = (
            f"\n{'=' * 50}\n"
            f"ALERTA [{message.prioridade.value.upper()}]\n"
            f"{'=' * 50}\n"
            f"Titulo: {message.titulo}\n"
            f"Corpo:\n{message.corpo}\n"
            f"Timestamp: {message.timestamp}\n"
            f"{'=' * 50}\n"
        )
        logger.info(log_message)

        return AlertResult(
            success=True,
            channel=self.channel,
            message_id=f"console_{message.timestamp.timestamp()}",
        )

    async def health_check(self) -> bool:
        return True
