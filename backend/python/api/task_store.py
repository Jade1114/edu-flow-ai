"""In-memory async task store for long-running GA pipelines.

Stores task status + result in a dict. Runs blocking work in a thread pool
so FastAPI's event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from python import ml_logger


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskNotFoundError(KeyError):
    pass


_tasks: dict[str, dict[str, Any]] = {}
_executor = ThreadPoolExecutor(max_workers=2)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create(
    name: str,
    total_steps: int = 100,
) -> str:
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "task_id": task_id,
        "name": name,
        "status": TaskStatus.PENDING,
        "progress": 0,
        "total_steps": total_steps,
        "result": None,
        "error": None,
        "created_at": _now(),
        "started_at": None,
        "completed_at": None,
    }
    return task_id


def get(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")
    return task


def update(task_id: str, **kwargs: Any) -> None:
    if task_id in _tasks:
        _tasks[task_id].update(kwargs)


def delete(task_id: str) -> None:
    _tasks.pop(task_id, None)


async def run_blocking(
    task_id: str,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Execute a blocking function in a thread, storing its result or error."""
    update(task_id, status=TaskStatus.RUNNING, started_at=_now())
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, fn, *args, **kwargs)
        update(
            task_id,
            status=TaskStatus.DONE,
            result=result,
            progress=100,
            completed_at=_now(),
        )
        ml_logger.service.info("Task completed: task_id=%s name=%s", task_id, _tasks[task_id]["name"])
    except Exception as exc:
        update(
            task_id,
            status=TaskStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}",
            completed_at=_now(),
        )
        ml_logger.service.error("Task failed: task_id=%s name=%s error=%s", task_id, _tasks[task_id]["name"], exc)


def cleanup_old_tasks(max_age_minutes: int = 60) -> int:
    """Remove tasks older than max_age_minutes. Returns count removed."""
    now = datetime.now()
    removed = 0
    for task_id, task in list(_tasks.items()):
        created = task.get("created_at")
        if created:
            age = (now - datetime.fromisoformat(created)).total_seconds()
            if age > max_age_minutes * 60:
                del _tasks[task_id]
                removed += 1
    return removed
