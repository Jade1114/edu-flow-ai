"""GA scheme generation endpoints — async task pattern.

POST  /api/ml/generate-scheme   → 202 Accepted + task_id (background GA run)
GET   /api/ml/generate-scheme/{task_id}  → task status + result when done
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse

import ml_logger

try:
    from .. import task_store
    from ..schemas import GenerateSchemeRequest, TaskStatusResponse
except ImportError:
    import task_store
    from schemas import GenerateSchemeRequest, TaskStatusResponse

router = APIRouter(tags=["ga"])


def _run_pipeline_by_task(task_id: int, ml_dir: Path) -> dict[str, Any]:
    """Blocking wrapper — imports GA module, runs by task_id."""
    scripts_dir = str(ml_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import generate_scheme_ga  # noqa: F811

    return generate_scheme_ga.run_ga_pipeline_by_task(
        task_id=task_id,
    )


@router.post("/generate-scheme", status_code=202)
async def submit_generate_scheme(
    request: Request,
    req: GenerateSchemeRequest | None = Body(default=None),
    task_id_query: int | None = Query(default=None, alias="task_id"),
) -> JSONResponse:
    """Submit a GA scheme generation task by task_id.

    Python reads everything from DB — Java only needs to pass task_id.
    Accepts task_id from JSON body or query param for client compatibility.
    Returns immediately with a task_id; poll GET /api/ml/generate-scheme/{task_id}.
    """
    allocation_task_id = req.task_id if req is not None else task_id_query
    if allocation_task_id is None:
        raise HTTPException(status_code=400, detail="Missing task_id in JSON body or query parameter")

    ml_dir: Path = request.app.state.ml_dir

    # Create async task
    task_id = task_store.create(
        name=f"GA scheme generation → task_{allocation_task_id}",
        total_steps=100,
    )

    ml_logger.service.info(
        "GA task submitted: task_id=%s allocation_task_id=%d source=%s",
        task_id, allocation_task_id, "body" if req is not None else "query",
    )

    # Fire & forget in thread pool
    asyncio.create_task(task_store.run_blocking(
        task_id,
        _run_pipeline_by_task,
        allocation_task_id,
        ml_dir,
    ))

    return JSONResponse(
        content={
            "task_id": task_id,
            "status_url": f"/api/ml/generate-scheme/{task_id}",
            "status": task_store.get(task_id)["status"],
            "message": "GA generation submitted, poll status_url for result",
        },
        status_code=202,
    )


@router.get("/generate-scheme/{task_id}", response_model=TaskStatusResponse)
async def get_generate_scheme_status(task_id: str) -> TaskStatusResponse:
    """Poll task status. Returns result once the GA pipeline finishes."""
    try:
        task = task_store.get(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        error=task.get("error"),
        result=task.get("result"),
        created_at=task.get("created_at"),
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
    )
