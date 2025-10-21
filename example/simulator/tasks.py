"""Asynchronous task orchestration for DPS simulations."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import uuid4

from . import data, simulation


@dataclass
class TaskResult:
    summary: simulation.SimulationSummary


@dataclass
class TaskState:
    task_id: str
    status: str
    result: Optional[TaskResult] = None
    error: Optional[str] = None


class TaskManager:
    """Manages long running simulations started through the REST API."""

    def __init__(self, repository: data.DataRepository):
        self._repository = repository
        self._tasks: Dict[str, TaskState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def create_task(
        self, build: simulation.PlayerBuild, config: simulation.SimulationConfig
    ) -> TaskState:
        task_id = uuid4().hex
        state = TaskState(task_id=task_id, status="pending")
        self._tasks[task_id] = state
        self._locks[task_id] = asyncio.Lock()

        async def runner() -> None:
            simulator = simulation.SimpleSimulator(self._repository)
            try:
                summary = await asyncio.get_running_loop().run_in_executor(
                    None, simulator.run, build, config
                )
            except Exception as exc:  # pragma: no cover - surfaced to HTTP client
                async with self._locks[task_id]:
                    state.status = "error"
                    state.error = str(exc)
                return

            async with self._locks[task_id]:
                state.status = "finished"
                state.result = TaskResult(summary=summary)

        asyncio.create_task(runner())
        return state

    async def get_task(self, task_id: str) -> TaskState:
        state = self._tasks.get(task_id)
        if not state:
            raise KeyError(task_id)
        async with self._locks[task_id]:
            return TaskState(
                task_id=state.task_id,
                status=state.status,
                result=state.result,
                error=state.error,
            )

