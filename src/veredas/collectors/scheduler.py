"""
Scheduler para coleta automatica de dados.

Permite agendar coletas periodicas dos coletores de forma programatica.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Callable, Optional

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult


class FrequencyType(str, Enum):
    """Tipos de frequencia de coleta."""

    ONCE = "once"  # Executa uma vez
    HOURLY = "hourly"  # A cada N horas
    DAILY = "daily"  # Diariamente em horario especifico
    WEEKLY = "weekly"  # Semanalmente
    INTERVAL = "interval"  # A cada N segundos


@dataclass
class ScheduledTask:
    """Tarefa agendada para coleta."""

    task_id: str
    collector: BaseCollector
    frequency: FrequencyType
    next_run: datetime
    last_run: Optional[datetime] = None
    enabled: bool = True

    # Parametros de frequencia
    interval_seconds: int = 3600  # Para HOURLY e INTERVAL
    time_of_day: Optional[time] = None  # Para DAILY
    day_of_week: int = 0  # Para WEEKLY (0=Monday, 6=Sunday)

    # Callback opcional apos coleta
    on_complete: Optional[Callable[[CollectionResult], None]] = None

    # Estatisticas
    run_count: int = 0
    success_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)


class CollectionScheduler:
    """
    Agendador de coletas automaticas.

    Permite agendar coletas periodicas de diferentes coletores
    com diferentes frequencias.

    Exemplo:
        scheduler = CollectionScheduler()

        # Coletar BCB diariamente as 8h
        scheduler.add_daily(
            task_id="bcb_daily",
            collector=BCBCollector(),
            time_of_day=time(8, 0)
        )

        # Coletar IFData a cada 6 horas
        scheduler.add_hourly(
            task_id="ifdata_6h",
            collector=IFDataCollector(),
            hours=6
        )

        # Executar scheduler
        await scheduler.run()
    """

    def __init__(self):
        """Inicializa o scheduler."""
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_task(self, task: ScheduledTask) -> None:
        """
        Adiciona uma tarefa ao scheduler.

        Args:
            task: Tarefa agendada.
        """
        self.tasks[task.task_id] = task

    def add_once(
        self,
        task_id: str,
        collector: BaseCollector,
        delay_seconds: int = 0,
        on_complete: Optional[Callable[[CollectionResult], None]] = None,
    ) -> ScheduledTask:
        """
        Agenda coleta unica.

        Args:
            task_id: ID da tarefa.
            collector: Coletor a executar.
            delay_seconds: Delay em segundos antes de executar.
            on_complete: Callback opcional.

        Returns:
            Tarefa criada.
        """
        task = ScheduledTask(
            task_id=task_id,
            collector=collector,
            frequency=FrequencyType.ONCE,
            next_run=datetime.now(TZ_BRASIL) + timedelta(seconds=delay_seconds),
            on_complete=on_complete,
        )
        self.add_task(task)
        return task

    def add_hourly(
        self,
        task_id: str,
        collector: BaseCollector,
        hours: int = 1,
        on_complete: Optional[Callable[[CollectionResult], None]] = None,
    ) -> ScheduledTask:
        """
        Agenda coleta a cada N horas.

        Args:
            task_id: ID da tarefa.
            collector: Coletor a executar.
            hours: Intervalo em horas.
            on_complete: Callback opcional.

        Returns:
            Tarefa criada.
        """
        task = ScheduledTask(
            task_id=task_id,
            collector=collector,
            frequency=FrequencyType.HOURLY,
            next_run=datetime.now(TZ_BRASIL),
            interval_seconds=hours * 3600,
            on_complete=on_complete,
        )
        self.add_task(task)
        return task

    def add_daily(
        self,
        task_id: str,
        collector: BaseCollector,
        time_of_day: time,
        on_complete: Optional[Callable[[CollectionResult], None]] = None,
    ) -> ScheduledTask:
        """
        Agenda coleta diaria em horario especifico.

        Args:
            task_id: ID da tarefa.
            collector: Coletor a executar.
            time_of_day: Horario de execucao.
            on_complete: Callback opcional.

        Returns:
            Tarefa criada.
        """
        now = datetime.now(TZ_BRASIL)
        next_run = datetime.combine(now.date(), time_of_day, tzinfo=TZ_BRASIL)

        # Se ja passou hoje, agendar para amanha
        if next_run < now:
            next_run += timedelta(days=1)

        task = ScheduledTask(
            task_id=task_id,
            collector=collector,
            frequency=FrequencyType.DAILY,
            next_run=next_run,
            time_of_day=time_of_day,
            on_complete=on_complete,
        )
        self.add_task(task)
        return task

    def add_interval(
        self,
        task_id: str,
        collector: BaseCollector,
        seconds: int,
        on_complete: Optional[Callable[[CollectionResult], None]] = None,
    ) -> ScheduledTask:
        """
        Agenda coleta a cada N segundos.

        Args:
            task_id: ID da tarefa.
            collector: Coletor a executar.
            seconds: Intervalo em segundos.
            on_complete: Callback opcional.

        Returns:
            Tarefa criada.
        """
        task = ScheduledTask(
            task_id=task_id,
            collector=collector,
            frequency=FrequencyType.INTERVAL,
            next_run=datetime.now(TZ_BRASIL),
            interval_seconds=seconds,
            on_complete=on_complete,
        )
        self.add_task(task)
        return task

    def remove_task(self, task_id: str) -> bool:
        """
        Remove uma tarefa do scheduler.

        Args:
            task_id: ID da tarefa.

        Returns:
            True se removida, False se nao encontrada.
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """Habilita uma tarefa."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Desabilita uma tarefa."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            return True
        return False

    async def _execute_task(self, task: ScheduledTask) -> None:
        """
        Executa uma tarefa de coleta.

        Args:
            task: Tarefa a executar.
        """
        try:
            # Executar coleta
            result = await task.collector.collect()

            # Atualizar estatisticas
            task.run_count += 1
            task.last_run = datetime.now(TZ_BRASIL)

            if result.success:
                task.success_count += 1
            else:
                task.error_count += 1
                if result.error:
                    task.errors.append(f"{datetime.now(TZ_BRASIL)}: {result.error}")
                    # Manter apenas ultimos 10 erros
                    task.errors = task.errors[-10:]

            # Callback opcional
            if task.on_complete:
                task.on_complete(result)

        except Exception as e:
            task.error_count += 1
            task.errors.append(f"{datetime.now(TZ_BRASIL)}: {str(e)}")
            task.errors = task.errors[-10:]

    def _calculate_next_run(self, task: ScheduledTask) -> datetime:
        """
        Calcula proximo horario de execucao.

        Args:
            task: Tarefa.

        Returns:
            Proximo horario de execucao.
        """
        now = datetime.now(TZ_BRASIL)

        if task.frequency == FrequencyType.ONCE:
            # Tarefa unica nao reexecuta
            return datetime.max

        elif task.frequency == FrequencyType.HOURLY:
            return now + timedelta(seconds=task.interval_seconds)

        elif task.frequency == FrequencyType.DAILY:
            if task.time_of_day:
                next_run = datetime.combine(now.date(), task.time_of_day, tzinfo=TZ_BRASIL)
                if next_run < now:
                    next_run += timedelta(days=1)
                return next_run
            return now + timedelta(days=1)

        elif task.frequency == FrequencyType.WEEKLY:
            # Calcular próximo dia da semana especificado
            dias_ate_proximo = (task.day_of_week - now.weekday()) % 7
            if dias_ate_proximo == 0:
                # Mesmo dia da semana, verificar se já passou o horário
                if task.time_of_day:
                    next_run = datetime.combine(now.date(), task.time_of_day, tzinfo=TZ_BRASIL)
                    if next_run <= now:
                        dias_ate_proximo = 7  # Próxima semana
                else:
                    dias_ate_proximo = 7  # Próxima semana

            next_date = now.date() + timedelta(days=dias_ate_proximo)
            if task.time_of_day:
                return datetime.combine(next_date, task.time_of_day, tzinfo=TZ_BRASIL)
            return datetime.combine(next_date, now.time(), tzinfo=TZ_BRASIL)

        elif task.frequency == FrequencyType.INTERVAL:
            return now + timedelta(seconds=task.interval_seconds)

        return now + timedelta(hours=1)

    async def run(self, max_iterations: Optional[int] = None) -> None:
        """
        Executa o scheduler em loop infinito.

        Args:
            max_iterations: Numero maximo de iteracoes (None = infinito).
        """
        self._running = True
        iterations = 0

        try:
            while self._running:
                now = datetime.now(TZ_BRASIL)

                # Verificar tarefas que precisam executar
                for task in list(self.tasks.values()):
                    if not task.enabled:
                        continue

                    if task.next_run <= now:
                        await self._execute_task(task)

                        # Calcular proximo horario
                        task.next_run = self._calculate_next_run(task)

                        # Remover tarefas ONCE apos execucao
                        if task.frequency == FrequencyType.ONCE:
                            self.remove_task(task.task_id)

                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break

                # Sleep por 1 segundo
                await asyncio.sleep(1)

            # Loop exited normally
            self._running = False

        except asyncio.CancelledError:
            self._running = False
            raise

    def start(self) -> asyncio.Task:
        """
        Inicia o scheduler em background.

        Returns:
            Task do asyncio.
        """
        if self._task and not self._task.done():
            raise RuntimeError("Scheduler ja esta executando")

        self._running = True
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        """Para o scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_status(self) -> dict:
        """
        Retorna status do scheduler.

        Returns:
            Dicionario com status.
        """
        return {
            "running": self._running,
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "collector": task.collector.source_name,
                    "frequency": task.frequency,
                    "enabled": task.enabled,
                    "next_run": task.next_run.isoformat(),
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "run_count": task.run_count,
                    "success_count": task.success_count,
                    "error_count": task.error_count,
                }
                for task in self.tasks.values()
            ],
        }
