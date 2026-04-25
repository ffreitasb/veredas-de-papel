"""
Scheduler para coleta automatica de dados.

Permite agendar coletas periodicas dos coletores de forma programatica.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from enum import StrEnum

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class FrequencyType(StrEnum):
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
    last_run: datetime | None = None
    enabled: bool = True

    # Parametros de frequencia
    interval_seconds: int = 3600  # Para HOURLY e INTERVAL
    time_of_day: time | None = None  # Para DAILY
    day_of_week: int = 0  # Para WEEKLY (0=Monday, 6=Sunday)

    # Callback opcional apos coleta
    on_complete: Callable[[CollectionResult], None] | None = None

    # Timeout para execucao (segundos, 0 = sem limite)
    timeout_seconds: int = 300  # 5 minutos padrao

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

    def __init__(self, check_interval: float = 1.0):
        """
        Inicializa o scheduler.

        Args:
            check_interval: Intervalo em segundos entre verificacoes de tasks (default: 1.0).
        """
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self.check_interval = check_interval

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
        on_complete: Callable[[CollectionResult], None] | None = None,
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
        on_complete: Callable[[CollectionResult], None] | None = None,
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
        on_complete: Callable[[CollectionResult], None] | None = None,
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
        on_complete: Callable[[CollectionResult], None] | None = None,
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
        """
        Habilita uma tarefa (imutavel).

        Args:
            task_id: ID da tarefa.

        Returns:
            True se habilitada, False se nao encontrada.
        """
        if task_id in self.tasks:
            self.tasks[task_id] = replace(self.tasks[task_id], enabled=True)
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """
        Desabilita uma tarefa (imutavel).

        Args:
            task_id: ID da tarefa.

        Returns:
            True se desabilitada, False se nao encontrada.
        """
        if task_id in self.tasks:
            self.tasks[task_id] = replace(self.tasks[task_id], enabled=False)
            return True
        return False

    async def _execute_task(self, task: ScheduledTask) -> ScheduledTask:
        """
        Executa uma tarefa de coleta.

        Usa imutabilidade: retorna uma NOVA instancia de ScheduledTask
        com as estatisticas atualizadas, ao inves de mutar o objeto original.

        Args:
            task: Tarefa a executar.

        Returns:
            Nova instancia de ScheduledTask com estatisticas atualizadas.
        """
        now = datetime.now(TZ_BRASIL)

        try:
            # Executar coleta com timeout (MEDIUM-004 security fix)
            timeout = task.timeout_seconds if task.timeout_seconds > 0 else None
            if timeout:
                result = await asyncio.wait_for(
                    task.collector.collect(),
                    timeout=timeout,
                )
            else:
                result = await task.collector.collect()

            # Criar nova lista de erros (imutabilidade)
            new_errors = task.errors.copy()

            if result.success:
                updated_task = replace(
                    task,
                    run_count=task.run_count + 1,
                    last_run=now,
                    success_count=task.success_count + 1,
                )
            else:
                if result.error:
                    new_errors.append(f"{now}: {result.error}")
                    new_errors = new_errors[-10:]  # Manter ultimos 10

                updated_task = replace(
                    task,
                    run_count=task.run_count + 1,
                    last_run=now,
                    error_count=task.error_count + 1,
                    errors=new_errors,
                )

            # Callback opcional com tratamento de excecao (M6)
            if task.on_complete:
                try:
                    task.on_complete(result)
                except Exception as callback_error:
                    logger.warning("Erro em callback da task %s: %s", task.task_id, callback_error)

            return updated_task

        except TimeoutError:
            new_errors = task.errors.copy()
            new_errors.append(f"{now}: Timeout apos {task.timeout_seconds}s")
            new_errors = new_errors[-10:]

            logger.warning("Task %s timeout apos %ss", task.task_id, task.timeout_seconds)

            return replace(
                task,
                run_count=task.run_count + 1,
                last_run=now,
                error_count=task.error_count + 1,
                errors=new_errors,
            )

        except Exception as e:
            new_errors = task.errors.copy()
            new_errors.append(f"{now}: {e!s}")
            new_errors = new_errors[-10:]

            logger.exception("Erro em task %s", task.task_id)

            return replace(
                task,
                run_count=task.run_count + 1,
                last_run=now,
                error_count=task.error_count + 1,
                errors=new_errors,
            )

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

    async def run(self, max_iterations: int | None = None) -> None:
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
                        # Executar e obter nova instancia (imutabilidade - M1)
                        updated_task = await self._execute_task(task)

                        # Calcular proximo horario e atualizar dict com nova instancia
                        updated_task = replace(
                            updated_task,
                            next_run=self._calculate_next_run(updated_task),
                        )
                        self.tasks[task.task_id] = updated_task

                        # Remover tarefas ONCE apos execucao
                        if updated_task.frequency == FrequencyType.ONCE:
                            self.remove_task(updated_task.task_id)

                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break

                # Sleep configuravel (L1)
                await asyncio.sleep(self.check_interval)

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
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

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
