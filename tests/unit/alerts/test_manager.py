"""Testes unitários para AlertManager — filtro de severidade e cooldown."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veredas import TZ_BRASIL
from veredas.alerts.base import AlertChannel, AlertResult
from veredas.alerts.manager import AlertManager
from veredas.storage.models import Anomalia, Severidade, TipoAnomalia

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_anomalia(severidade: Severidade, id: int = 1) -> Anomalia:
    """Cria Anomalia sem sessão de banco para testes unitários."""
    from datetime import datetime

    a = Anomalia()
    a.id = id
    a.if_id = 1
    a.severidade = severidade
    a.tipo = TipoAnomalia.SPREAD_ALTO
    a.valor_detectado = Decimal("120.0")
    a.descricao = "Teste"
    a.detectado_em = datetime.now(TZ_BRASIL)
    a.resolvido = False
    a.instituicao = None
    return a


def _make_sender(success: bool = True) -> MagicMock:
    sender = MagicMock()
    sender.is_configured = True
    sender.channel = AlertChannel.CONSOLE
    result = AlertResult(success=success, channel=AlertChannel.CONSOLE)
    sender.send = AsyncMock(return_value=result)
    return sender


def _manager(min_severity: str = "medium", cooldown: int = 60) -> AlertManager:
    with patch("veredas.alerts.manager.get_settings") as mock_settings:
        mock_settings.return_value.alerts.alert_min_severity = min_severity
        mock_settings.return_value.alerts.alert_cooldown_minutes = cooldown
        return AlertManager(senders=[])


# ---------------------------------------------------------------------------
# _should_alert — filtro de severidade
# ---------------------------------------------------------------------------


class TestShouldAlertSeverity:
    def test_abaixo_do_minimo_bloqueado(self):
        mgr = _manager(min_severity="high")
        anomalia = _make_anomalia(Severidade.LOW)
        deve, motivo = mgr._should_alert(anomalia)
        assert not deve
        assert "abaixo do minimo" in motivo

    def test_igual_ao_minimo_passa(self):
        mgr = _manager(min_severity="medium")
        anomalia = _make_anomalia(Severidade.MEDIUM)
        deve, motivo = mgr._should_alert(anomalia)
        assert deve
        assert motivo is None

    def test_acima_do_minimo_passa(self):
        mgr = _manager(min_severity="low")
        anomalia = _make_anomalia(Severidade.CRITICAL)
        deve, motivo = mgr._should_alert(anomalia)
        assert deve

    @pytest.mark.parametrize(
        "min_sev, anomalia_sev, expected",
        [
            ("low", Severidade.LOW, True),
            ("low", Severidade.CRITICAL, True),
            ("medium", Severidade.LOW, False),
            ("medium", Severidade.MEDIUM, True),
            ("medium", Severidade.HIGH, True),
            ("high", Severidade.MEDIUM, False),
            ("high", Severidade.HIGH, True),
            ("high", Severidade.CRITICAL, True),
            ("critical", Severidade.HIGH, False),
            ("critical", Severidade.CRITICAL, True),
        ],
    )
    def test_matriz_de_severidade(self, min_sev, anomalia_sev, expected):
        mgr = _manager(min_severity=min_sev)
        anomalia = _make_anomalia(anomalia_sev)
        deve, _ = mgr._should_alert(anomalia)
        assert deve == expected

    def test_min_severity_invalido_bloqueia_e_loga(self, caplog):
        """Configuração inválida não deve silenciosamente alertar tudo."""
        import logging

        mgr = _manager(min_severity="hight")  # typo intencional
        anomalia = _make_anomalia(Severidade.CRITICAL)
        with caplog.at_level(logging.WARNING, logger="veredas.alerts.manager"):
            deve, motivo = mgr._should_alert(anomalia)
        assert not deve
        assert "inválida" in motivo.lower() or "invalida" in motivo.lower()
        assert any("inválida" in r.message or "invalida" in r.message for r in caplog.records)

    def test_anomalia_severity_invalida_bloqueia(self, caplog):
        import logging

        mgr = _manager(min_severity="low")
        anomalia = _make_anomalia(Severidade.HIGH)
        anomalia.severidade = "ultraviolet"  # valor inválido
        with caplog.at_level(logging.WARNING, logger="veredas.alerts.manager"):
            deve, _ = mgr._should_alert(anomalia)
        assert not deve


# ---------------------------------------------------------------------------
# _should_alert — cooldown
# ---------------------------------------------------------------------------


class TestShouldAlertCooldown:
    def test_cooldown_ativo_bloqueia(self):
        from datetime import datetime

        mgr = _manager(min_severity="low", cooldown=60)
        anomalia = _make_anomalia(Severidade.HIGH, id=42)
        # Injeta timestamp recente no histórico
        mgr._alert_history[42] = datetime.now(TZ_BRASIL)
        deve, motivo = mgr._should_alert(anomalia)
        assert not deve
        assert "Cooldown ativo" in motivo

    def test_cooldown_expirado_permite(self):
        from datetime import datetime

        mgr = _manager(min_severity="low", cooldown=1)
        anomalia = _make_anomalia(Severidade.HIGH, id=99)
        # Injeta timestamp 2 minutos atrás
        mgr._alert_history[99] = datetime.now(TZ_BRASIL) - timedelta(minutes=2)
        deve, motivo = mgr._should_alert(anomalia)
        assert deve
        assert motivo is None

    def test_sem_historico_permite(self):
        mgr = _manager(min_severity="low", cooldown=60)
        anomalia = _make_anomalia(Severidade.HIGH, id=7)
        deve, motivo = mgr._should_alert(anomalia)
        assert deve

    def test_anomalia_sem_id_ignora_cooldown(self):
        """Anomalia transiente (id=None) não deve causar KeyError no histórico."""
        mgr = _manager(min_severity="low", cooldown=60)
        anomalia = _make_anomalia(Severidade.HIGH)
        anomalia.id = None
        deve, _ = mgr._should_alert(anomalia)
        assert deve


# ---------------------------------------------------------------------------
# notify — integração com senders mock
# ---------------------------------------------------------------------------


class TestNotify:
    @pytest.mark.asyncio
    async def test_notify_envia_para_sender_configurado(self):
        mgr = _manager(min_severity="low")
        sender = _make_sender(success=True)
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.HIGH)
        resultados = await mgr.notify(anomalia)

        sender.send.assert_awaited_once()
        assert resultados[0].success

    @pytest.mark.asyncio
    async def test_notify_bloqueia_por_severidade(self):
        mgr = _manager(min_severity="critical")
        sender = _make_sender()
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.LOW)
        resultados = await mgr.notify(anomalia)

        sender.send.assert_not_awaited()
        assert not resultados[0].success
        assert "abaixo do minimo" in resultados[0].error

    @pytest.mark.asyncio
    async def test_notify_sem_senders_retorna_erro(self):
        mgr = _manager(min_severity="low")
        anomalia = _make_anomalia(Severidade.HIGH)
        resultados = await mgr.notify(anomalia)
        assert not resultados[0].success
        assert "Nenhum canal" in resultados[0].error

    @pytest.mark.asyncio
    async def test_notify_sucesso_registra_historico(self):
        mgr = _manager(min_severity="low", cooldown=60)
        sender = _make_sender(success=True)
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.HIGH, id=55)
        await mgr.notify(anomalia)

        assert 55 in mgr._alert_history

    @pytest.mark.asyncio
    async def test_notify_falha_nao_registra_historico(self):
        mgr = _manager(min_severity="low", cooldown=60)
        sender = _make_sender(success=False)
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.HIGH, id=56)
        await mgr.notify(anomalia)

        assert 56 not in mgr._alert_history

    @pytest.mark.asyncio
    async def test_notify_cooldown_bloqueia_segundo_envio(self):
        mgr = _manager(min_severity="low", cooldown=60)
        sender = _make_sender(success=True)
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.HIGH, id=77)
        await mgr.notify(anomalia)
        await mgr.notify(anomalia)

        # Segundo notify bloqueado pelo cooldown — sender chamado só 1 vez
        assert sender.send.await_count == 1

    @pytest.mark.asyncio
    async def test_notify_batch(self):
        mgr = _manager(min_severity="low")
        sender = _make_sender(success=True)
        mgr.senders = [sender]

        anomalias = [_make_anomalia(Severidade.HIGH, id=i) for i in range(1, 4)]
        resultados = await mgr.notify_batch(anomalias)

        assert len(resultados) == 3
        assert all(r[0].success for r in resultados.values())

    @pytest.mark.asyncio
    async def test_sender_exception_tratada(self):
        """Exceção em sender não deve propagar — deve retornar AlertResult de falha."""
        mgr = _manager(min_severity="low")
        sender = _make_sender()
        sender.send = AsyncMock(side_effect=RuntimeError("timeout"))
        mgr.senders = [sender]

        anomalia = _make_anomalia(Severidade.CRITICAL, id=88)
        resultados = await mgr.notify(anomalia)

        assert not resultados[0].success
        assert "timeout" in resultados[0].error


# ---------------------------------------------------------------------------
# clear_history / add_sender / remove_sender
# ---------------------------------------------------------------------------


class TestManagerUtils:
    def test_clear_history(self):
        from datetime import datetime

        mgr = _manager()
        mgr._alert_history[1] = datetime.now(TZ_BRASIL)
        mgr.clear_history()
        assert len(mgr._alert_history) == 0

    def test_add_remove_sender(self):
        mgr = _manager()
        sender = _make_sender()
        mgr.add_sender(sender)
        assert sender in mgr.senders
        removed = mgr.remove_sender(AlertChannel.CONSOLE)
        assert removed
        assert sender not in mgr.senders

    def test_remove_sender_inexistente_retorna_false(self):
        mgr = _manager()
        assert not mgr.remove_sender(AlertChannel.EMAIL)
