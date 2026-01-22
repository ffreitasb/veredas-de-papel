"""
Testes do scheduler de coletas.
"""

import asyncio
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from veredas import TZ_BRASIL
from veredas.collectors.base import CollectionResult
from veredas.collectors.scheduler import (
    CollectionScheduler,
    FrequencyType,
    ScheduledTask,
)


class MockCollector:
    """Coletor mock para testes."""

    def __init__(self, source_name: str = "mock", should_fail: bool = False):
        self.source_name = source_name
        self.should_fail = should_fail
        self.call_count = 0

    async def collect(self):
        """Mock de coleta."""
        self.call_count += 1
        if self.should_fail:
            return CollectionResult.fail(error="Mock error", source=self.source_name)
        return CollectionResult.ok(data={"mock": True}, source=self.source_name)


class TestScheduledTask:
    """Testes do ScheduledTask."""

    def test_create_scheduled_task(self):
        """Testa criacao de tarefa agendada."""
        collector = MockCollector()
        next_run = datetime.now(TZ_BRASIL) + timedelta(hours=1)

        task = ScheduledTask(
            task_id="test_task",
            collector=collector,
            frequency=FrequencyType.HOURLY,
            next_run=next_run,
            interval_seconds=3600,
        )

        assert task.task_id == "test_task"
        assert task.collector == collector
        assert task.frequency == FrequencyType.HOURLY
        assert task.next_run == next_run
        assert task.enabled is True
        assert task.run_count == 0
        assert task.success_count == 0
        assert task.error_count == 0

    def test_scheduled_task_with_callback(self):
        """Testa tarefa com callback."""
        collector = MockCollector()
        callback = MagicMock()

        task = ScheduledTask(
            task_id="test_task",
            collector=collector,
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL),
            on_complete=callback,
        )

        assert task.on_complete == callback


class TestCollectionScheduler:
    """Testes do CollectionScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Fixture do scheduler."""
        return CollectionScheduler()

    @pytest.fixture
    def mock_collector(self):
        """Fixture de coletor mock."""
        return MockCollector()

    def test_create_scheduler(self, scheduler: CollectionScheduler):
        """Testa criacao do scheduler."""
        assert len(scheduler.tasks) == 0
        assert scheduler._running is False

    def test_add_once(self, scheduler: CollectionScheduler, mock_collector: MockCollector):
        """Testa adicionar tarefa unica."""
        task = scheduler.add_once(
            task_id="test_once",
            collector=mock_collector,
            delay_seconds=10,
        )

        assert task.task_id == "test_once"
        assert task.frequency == FrequencyType.ONCE
        assert task.collector == mock_collector
        assert "test_once" in scheduler.tasks

    def test_add_hourly(self, scheduler: CollectionScheduler, mock_collector: MockCollector):
        """Testa adicionar tarefa por hora."""
        task = scheduler.add_hourly(
            task_id="test_hourly",
            collector=mock_collector,
            hours=2,
        )

        assert task.task_id == "test_hourly"
        assert task.frequency == FrequencyType.HOURLY
        assert task.interval_seconds == 7200  # 2 hours
        assert "test_hourly" in scheduler.tasks

    def test_add_daily(self, scheduler: CollectionScheduler, mock_collector: MockCollector):
        """Testa adicionar tarefa diaria."""
        target_time = time(8, 0)
        task = scheduler.add_daily(
            task_id="test_daily",
            collector=mock_collector,
            time_of_day=target_time,
        )

        assert task.task_id == "test_daily"
        assert task.frequency == FrequencyType.DAILY
        assert task.time_of_day == target_time
        assert "test_daily" in scheduler.tasks

    def test_add_interval(self, scheduler: CollectionScheduler, mock_collector: MockCollector):
        """Testa adicionar tarefa por intervalo."""
        task = scheduler.add_interval(
            task_id="test_interval",
            collector=mock_collector,
            seconds=60,
        )

        assert task.task_id == "test_interval"
        assert task.frequency == FrequencyType.INTERVAL
        assert task.interval_seconds == 60
        assert "test_interval" in scheduler.tasks

    def test_remove_task(self, scheduler: CollectionScheduler, mock_collector: MockCollector):
        """Testa remover tarefa."""
        scheduler.add_once(task_id="to_remove", collector=mock_collector)
        assert "to_remove" in scheduler.tasks

        result = scheduler.remove_task("to_remove")
        assert result is True
        assert "to_remove" not in scheduler.tasks

        # Tentar remover novamente
        result = scheduler.remove_task("to_remove")
        assert result is False

    def test_enable_disable_task(
        self, scheduler: CollectionScheduler, mock_collector: MockCollector
    ):
        """Testa habilitar/desabilitar tarefa."""
        scheduler.add_once(task_id="test_task", collector=mock_collector)

        # Desabilitar
        result = scheduler.disable_task("test_task")
        assert result is True
        assert scheduler.tasks["test_task"].enabled is False

        # Habilitar
        result = scheduler.enable_task("test_task")
        assert result is True
        assert scheduler.tasks["test_task"].enabled is True

        # Task nao existe
        assert scheduler.enable_task("nonexistent") is False
        assert scheduler.disable_task("nonexistent") is False

    @pytest.mark.asyncio
    async def test_execute_task_success(
        self, scheduler: CollectionScheduler, mock_collector: MockCollector
    ):
        """Testa execucao de tarefa com sucesso."""
        task = ScheduledTask(
            task_id="test_task",
            collector=mock_collector,
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL),
        )

        await scheduler._execute_task(task)

        assert task.run_count == 1
        assert task.success_count == 1
        assert task.error_count == 0
        assert mock_collector.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_task_failure(self, scheduler: CollectionScheduler):
        """Testa execucao de tarefa com falha."""
        failing_collector = MockCollector(should_fail=True)
        task = ScheduledTask(
            task_id="test_task",
            collector=failing_collector,
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL),
        )

        await scheduler._execute_task(task)

        assert task.run_count == 1
        assert task.success_count == 0
        assert task.error_count == 1
        assert len(task.errors) == 1

    @pytest.mark.asyncio
    async def test_execute_task_with_callback(
        self, scheduler: CollectionScheduler, mock_collector: MockCollector
    ):
        """Testa execucao de tarefa com callback."""
        callback = MagicMock()
        task = ScheduledTask(
            task_id="test_task",
            collector=mock_collector,
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL),
            on_complete=callback,
        )

        await scheduler._execute_task(task)

        callback.assert_called_once()

    def test_calculate_next_run_once(self, scheduler: CollectionScheduler):
        """Testa calculo de proximo run para ONCE."""
        task = ScheduledTask(
            task_id="test",
            collector=MockCollector(),
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL),
        )

        next_run = scheduler._calculate_next_run(task)
        assert next_run == datetime.max  # Nao reexecuta

    def test_calculate_next_run_hourly(self, scheduler: CollectionScheduler):
        """Testa calculo de proximo run para HOURLY."""
        task = ScheduledTask(
            task_id="test",
            collector=MockCollector(),
            frequency=FrequencyType.HOURLY,
            next_run=datetime.now(TZ_BRASIL),
            interval_seconds=3600,
        )

        now = datetime.now(TZ_BRASIL)
        next_run = scheduler._calculate_next_run(task)

        # Deve ser aproximadamente 1 hora no futuro
        diff = (next_run - now).total_seconds()
        assert 3595 < diff < 3605  # ~1 hour with tolerance

    def test_calculate_next_run_daily(self, scheduler: CollectionScheduler):
        """Testa calculo de proximo run para DAILY."""
        target_time = time(8, 0)
        task = ScheduledTask(
            task_id="test",
            collector=MockCollector(),
            frequency=FrequencyType.DAILY,
            next_run=datetime.now(TZ_BRASIL),
            time_of_day=target_time,
        )

        next_run = scheduler._calculate_next_run(task)

        # Deve ser as 8h de hoje ou amanha
        assert next_run.hour == 8
        assert next_run.minute == 0

    @pytest.mark.asyncio
    async def test_run_with_max_iterations(
        self, scheduler: CollectionScheduler, mock_collector: MockCollector
    ):
        """Testa run com numero maximo de iteracoes."""
        scheduler.add_once(task_id="test", collector=mock_collector, delay_seconds=0)

        await scheduler.run(max_iterations=5)

        assert not scheduler._running
        assert mock_collector.call_count == 1  # Executou a tarefa

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler: CollectionScheduler):
        """Testa start e stop do scheduler."""
        # Start
        task = scheduler.start()
        assert scheduler._running
        assert not task.done()

        # Stop
        await scheduler.stop()
        assert not scheduler._running
        assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_start_already_running(self, scheduler: CollectionScheduler):
        """Testa start quando ja esta rodando."""
        scheduler.start()

        with pytest.raises(RuntimeError, match="ja esta executando"):
            scheduler.start()

        await scheduler.stop()

    def test_get_status_empty(self, scheduler: CollectionScheduler):
        """Testa get_status com scheduler vazio."""
        status = scheduler.get_status()

        assert status["running"] is False
        assert status["total_tasks"] == 0
        assert status["enabled_tasks"] == 0
        assert len(status["tasks"]) == 0

    def test_get_status_with_tasks(
        self, scheduler: CollectionScheduler, mock_collector: MockCollector
    ):
        """Testa get_status com tarefas."""
        scheduler.add_hourly(task_id="task1", collector=mock_collector)
        scheduler.add_daily(
            task_id="task2", collector=mock_collector, time_of_day=time(8, 0)
        )
        scheduler.disable_task("task2")

        status = scheduler.get_status()

        assert status["total_tasks"] == 2
        assert status["enabled_tasks"] == 1
        assert len(status["tasks"]) == 2

        # Verificar estrutura
        task_info = status["tasks"][0]
        assert "task_id" in task_info
        assert "collector" in task_info
        assert "frequency" in task_info
        assert "next_run" in task_info

    @pytest.mark.asyncio
    async def test_integration_multiple_tasks(self, scheduler: CollectionScheduler):
        """Testa integracao com multiplas tarefas."""
        collector1 = MockCollector("collector1")
        collector2 = MockCollector("collector2")

        # Adicionar tarefas que executam imediatamente
        scheduler.add_once(task_id="task1", collector=collector1, delay_seconds=0)
        scheduler.add_once(task_id="task2", collector=collector2, delay_seconds=0)

        # Executar por algumas iteracoes
        await scheduler.run(max_iterations=10)

        # Ambos coletores devem ter sido executados
        assert collector1.call_count == 1
        assert collector2.call_count == 1

        # Tarefas ONCE devem ter sido removidas
        assert "task1" not in scheduler.tasks
        assert "task2" not in scheduler.tasks
