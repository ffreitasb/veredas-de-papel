"""Testes unitários para collectors/scheduler.py — _calculate_next_run() com timezone."""

from datetime import date, datetime, time, timedelta
from unittest.mock import MagicMock, patch

import pytest

from veredas import TZ_BRASIL
from veredas.collectors.scheduler import CollectionScheduler, FrequencyType, ScheduledTask

# Data/hora fixa para todos os testes: segunda-feira 2024-06-03 às 10:30 BRT
FIXED_NOW = datetime(2024, 6, 3, 10, 30, 0, tzinfo=TZ_BRASIL)  # segunda = weekday 0


def _make_task(**kwargs) -> ScheduledTask:
    defaults = {
        "task_id": "test",
        "collector": MagicMock(),
        "frequency": FrequencyType.INTERVAL,
        "next_run": FIXED_NOW,
        "interval_seconds": 3600,
    }
    defaults.update(kwargs)
    return ScheduledTask(**defaults)


def _calc_next(task: ScheduledTask, now: datetime = FIXED_NOW) -> datetime:
    """Chama _calculate_next_run com 'now' fixo para testes determinísticos."""
    sched = CollectionScheduler()
    with patch("veredas.collectors.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.max = datetime.max
        mock_dt.combine = datetime.combine
        return sched._calculate_next_run(task)


# ---------------------------------------------------------------------------
# ONCE
# ---------------------------------------------------------------------------


class TestFrequencyOnce:
    def test_once_retorna_datetime_max(self):
        task = _make_task(frequency=FrequencyType.ONCE)
        result = _calc_next(task)
        assert result == datetime.max


# ---------------------------------------------------------------------------
# HOURLY / INTERVAL
# ---------------------------------------------------------------------------


class TestFrequencyHourlyInterval:
    def test_hourly_soma_interval_seconds(self):
        task = _make_task(frequency=FrequencyType.HOURLY, interval_seconds=3600)
        result = _calc_next(task)
        assert result == FIXED_NOW + timedelta(seconds=3600)

    def test_interval_soma_seconds_customizado(self):
        task = _make_task(frequency=FrequencyType.INTERVAL, interval_seconds=900)
        result = _calc_next(task)
        assert result == FIXED_NOW + timedelta(seconds=900)

    def test_interval_resultado_tem_timezone_brasil(self):
        task = _make_task(frequency=FrequencyType.INTERVAL, interval_seconds=60)
        result = _calc_next(task)
        assert result.tzinfo == TZ_BRASIL


# ---------------------------------------------------------------------------
# DAILY
# ---------------------------------------------------------------------------


class TestFrequencyDaily:
    def test_daily_com_horario_futuro_retorna_hoje(self):
        """11:00 é depois de 10:30 → deve retornar hoje às 11:00."""
        task = _make_task(
            frequency=FrequencyType.DAILY,
            time_of_day=time(11, 0, 0),
        )
        result = _calc_next(task)
        expected = datetime.combine(FIXED_NOW.date(), time(11, 0, 0), tzinfo=TZ_BRASIL)
        assert result == expected

    def test_daily_com_horario_passado_retorna_amanha(self):
        """09:00 é antes de 10:30 → deve retornar amanhã às 09:00."""
        task = _make_task(
            frequency=FrequencyType.DAILY,
            time_of_day=time(9, 0, 0),
        )
        result = _calc_next(task)
        amanha = FIXED_NOW.date() + timedelta(days=1)
        expected = datetime.combine(amanha, time(9, 0, 0), tzinfo=TZ_BRASIL)
        assert result == expected

    def test_daily_sem_time_of_day_soma_1_dia(self):
        task = _make_task(frequency=FrequencyType.DAILY, time_of_day=None)
        result = _calc_next(task)
        assert result == FIXED_NOW + timedelta(days=1)

    def test_daily_resultado_tem_timezone_brasil(self):
        task = _make_task(frequency=FrequencyType.DAILY, time_of_day=time(11, 0))
        result = _calc_next(task)
        assert result.tzinfo == TZ_BRASIL


# ---------------------------------------------------------------------------
# WEEKLY
# ---------------------------------------------------------------------------


class TestFrequencyWeekly:
    def test_weekly_dia_futuro_nesta_semana(self):
        """FIXED_NOW é segunda (0). Quarta (2) é daqui a 2 dias."""
        task = _make_task(
            frequency=FrequencyType.WEEKLY,
            day_of_week=2,  # quarta
            time_of_day=None,
        )
        result = _calc_next(task)
        expected_date = FIXED_NOW.date() + timedelta(days=2)
        assert result.date() == expected_date

    def test_weekly_mesmo_dia_sem_horario_vai_para_semana_seguinte(self):
        """Segunda sem time_of_day → dias_ate_proximo=0 → vai para 7 dias."""
        task = _make_task(
            frequency=FrequencyType.WEEKLY,
            day_of_week=0,  # segunda = hoje
            time_of_day=None,
        )
        result = _calc_next(task)
        expected_date = FIXED_NOW.date() + timedelta(days=7)
        assert result.date() == expected_date

    def test_weekly_mesmo_dia_horario_futuro_retorna_hoje(self):
        """Segunda com horário 11:00 (futuro): deve retornar hoje."""
        task = _make_task(
            frequency=FrequencyType.WEEKLY,
            day_of_week=0,  # segunda = hoje
            time_of_day=time(11, 0),
        )
        result = _calc_next(task)
        assert result.date() == FIXED_NOW.date()
        assert result.time() == time(11, 0)

    def test_weekly_mesmo_dia_horario_passado_vai_para_semana_seguinte(self):
        """Segunda com horário 09:00 (passado): deve retornar segunda que vem."""
        task = _make_task(
            frequency=FrequencyType.WEEKLY,
            day_of_week=0,
            time_of_day=time(9, 0),
        )
        result = _calc_next(task)
        expected_date = FIXED_NOW.date() + timedelta(days=7)
        assert result.date() == expected_date

    def test_weekly_com_time_of_day_aplica_horario(self):
        """Terça (1) com horário 14:00."""
        task = _make_task(
            frequency=FrequencyType.WEEKLY,
            day_of_week=1,  # terça = amanhã
            time_of_day=time(14, 0),
        )
        result = _calc_next(task)
        expected = datetime.combine(
            FIXED_NOW.date() + timedelta(days=1), time(14, 0), tzinfo=TZ_BRASIL
        )
        assert result == expected

    def test_weekly_resultado_tem_timezone_brasil(self):
        task = _make_task(frequency=FrequencyType.WEEKLY, day_of_week=2)
        result = _calc_next(task)
        assert result.tzinfo == TZ_BRASIL
