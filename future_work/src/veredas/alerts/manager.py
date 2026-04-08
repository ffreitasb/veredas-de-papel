"""
Gerenciador de alertas.

Orquestra o envio de alertas para multiplos canais,
gerencia cooldowns e filtra por severidade.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

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
from veredas.config import get_settings
from veredas.storage.models import Anomalia


class AlertManager:
    """
    Gerenciador central de alertas.

    Responsavel por:
    - Gerenciar multiplos canais de alerta
    - Aplicar filtros de severidade minima
    - Controlar cooldown entre alertas
    - Evitar duplicatas
    """

    def __init__(
        self,
        senders: Optional[list[AlertSender]] = None,
        min_severity: Optional[str] = None,
        cooldown_minutes: Optional[int] = None,
    ):
        """
        Inicializa o gerenciador de alertas.

        Args:
            senders: Lista de senders. Se None, cria automaticamente.
            min_severity: Severidade minima para alertar.
            cooldown_minutes: Minutos entre alertas da mesma anomalia.
        """
        settings = get_settings()

        self.min_severity = min_severity or settings.alert_min_severity
        self.cooldown_minutes = cooldown_minutes or settings.alert_cooldown_minutes

        # Historico de alertas enviados (anomalia_id -> timestamp)
        self._alert_history: dict[int, datetime] = {}

        # Inicializa senders
        if senders is not None:
            self.senders = senders
        else:
            self.senders = self._create_default_senders()

    def _create_default_senders(self) -> list[AlertSender]:
        """Cria senders baseado na configuracao do ambiente."""
        senders: list[AlertSender] = []

        # Email
        email_sender = EmailAlertSender()
        if email_sender.is_configured:
            senders.append(email_sender)

        # Telegram
        telegram_sender = TelegramAlertSender()
        if telegram_sender.is_configured:
            senders.append(telegram_sender)

        # Console sempre disponivel (para debug)
        # senders.append(ConsoleSender())

        return senders

    @property
    def channels_configured(self) -> list[AlertChannel]:
        """Retorna lista de canais configurados."""
        return [s.channel for s in self.senders if s.is_configured]

    def _should_alert(self, anomalia: Anomalia) -> tuple[bool, Optional[str]]:
        """
        Verifica se deve enviar alerta para a anomalia.

        Returns:
            Tupla (deve_alertar, motivo_se_nao)
        """
        # Verificar severidade minima
        severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        try:
            min_idx = severity_order.index(self.min_severity.upper())
            anomalia_idx = severity_order.index(anomalia.severidade.upper())

            if anomalia_idx < min_idx:
                return False, f"Severidade {anomalia.severidade} abaixo do minimo ({self.min_severity})"
        except ValueError:
            pass  # Severidade invalida, permite

        # Verificar cooldown
        if anomalia.id in self._alert_history:
            last_alert = self._alert_history[anomalia.id]
            cooldown = timedelta(minutes=self.cooldown_minutes)

            if datetime.now() - last_alert < cooldown:
                remaining = cooldown - (datetime.now() - last_alert)
                return False, f"Cooldown ativo ({remaining.seconds // 60}min restantes)"

        return True, None

    async def notify(self, anomalia: Anomalia) -> list[AlertResult]:
        """
        Envia alerta para todos os canais configurados.

        Args:
            anomalia: Anomalia a alertar.

        Returns:
            Lista de resultados por canal.
        """
        should_alert, reason = self._should_alert(anomalia)

        if not should_alert:
            return [
                AlertResult(
                    success=False,
                    channel=AlertChannel.CONSOLE,
                    error=reason,
                )
            ]

        if not self.senders:
            return [
                AlertResult(
                    success=False,
                    channel=AlertChannel.CONSOLE,
                    error="Nenhum canal de alerta configurado",
                )
            ]

        # Envia para todos os canais em paralelo
        message = AlertMessage.from_anomalia(anomalia)
        tasks = [sender.send(message) for sender in self.senders]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Processa resultados
        final_results: list[AlertResult] = []
        any_success = False

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    AlertResult(
                        success=False,
                        channel=self.senders[i].channel,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)
                if result.success:
                    any_success = True

        # Atualiza historico se pelo menos um envio teve sucesso
        if any_success:
            self._alert_history[anomalia.id] = datetime.now()

        return final_results

    async def notify_batch(
        self,
        anomalias: list[Anomalia],
    ) -> dict[int, list[AlertResult]]:
        """
        Envia alertas para multiplas anomalias.

        Args:
            anomalias: Lista de anomalias.

        Returns:
            Dicionario {anomalia_id: [resultados]}
        """
        results: dict[int, list[AlertResult]] = {}

        for anomalia in anomalias:
            results[anomalia.id] = await self.notify(anomalia)

        return results

    async def test_channels(self) -> dict[AlertChannel, bool]:
        """
        Testa todos os canais configurados.

        Returns:
            Dicionario {canal: esta_operacional}
        """
        results: dict[AlertChannel, bool] = {}

        for sender in self.senders:
            try:
                is_healthy = await sender.health_check()
                results[sender.channel] = is_healthy
            except Exception:
                results[sender.channel] = False

        return results

    async def send_test_alert(
        self,
        channel: Optional[AlertChannel] = None,
    ) -> list[AlertResult]:
        """
        Envia alerta de teste.

        Args:
            channel: Canal especifico para testar. Se None, testa todos.

        Returns:
            Lista de resultados.
        """
        test_message = AlertMessage(
            titulo="[TESTE] Alerta do veredas de papel",
            corpo="Este e um alerta de teste do sistema de monitoramento.\n"
                  "Se voce recebeu esta mensagem, o canal esta funcionando!",
            prioridade=AlertPriority.LOW,
        )

        if channel:
            # Envia apenas para canal especifico
            for sender in self.senders:
                if sender.channel == channel:
                    return [await sender.send(test_message)]

            return [
                AlertResult(
                    success=False,
                    channel=channel,
                    error=f"Canal {channel.value} nao configurado",
                )
            ]

        # Envia para todos
        tasks = [sender.send(test_message) for sender in self.senders]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if isinstance(r, AlertResult)
            else AlertResult(success=False, channel=AlertChannel.CONSOLE, error=str(r))
            for r in results
        ]

    def clear_history(self) -> None:
        """Limpa historico de alertas enviados."""
        self._alert_history.clear()

    def add_sender(self, sender: AlertSender) -> None:
        """Adiciona um sender de alertas."""
        self.senders.append(sender)

    def remove_sender(self, channel: AlertChannel) -> bool:
        """Remove sender de um canal especifico."""
        for i, sender in enumerate(self.senders):
            if sender.channel == channel:
                self.senders.pop(i)
                return True
        return False
