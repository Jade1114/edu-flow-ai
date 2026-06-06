"""V3 scheduling-chain endpoints."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from python.scheduling_v3.pipeline import (
    DEFAULT_GENERATION_MODE,
    DEFAULT_PLAN_COUNT,
    DEFAULT_TOP_K,
    MAX_PLAN_COUNT,
    MAX_SOLVER_TIME_LIMIT_SECONDS,
    MAX_TOP_K,
    run_v3_pipeline,
)

router = APIRouter(tags=["v3"])
_tasks: dict[str, dict] = {}
_events: dict[str, list[dict]] = {}
_event_queues: dict[str, list[asyncio.Queue]] = {}


class GenerateV3Request(BaseModel):
    allocation_task_id: int
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    plan_count: int = Field(default=DEFAULT_PLAN_COUNT, ge=1, le=MAX_PLAN_COUNT)
    scheme_count: int | None = Field(default=None, ge=1, le=20)
    solver_time_limit_seconds: float = Field(default=60.0, ge=1.0, le=MAX_SOLVER_TIME_LIMIT_SECONDS)
    solver_workers: int | None = Field(default=None, ge=1, le=32)
    generation_mode: str = DEFAULT_GENERATION_MODE
    max_auto_stage: str | None = None
    skip_diversity: bool = False
    output_dir: str | None = None


class GenerateSchemeRequest(BaseModel):
    task_id: int
    teacher_profiles_jsonl: str | None = None
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    plan_count: int = Field(default=DEFAULT_PLAN_COUNT, ge=1, le=MAX_PLAN_COUNT)
    scheme_count: int | None = Field(default=None, ge=1, le=20)
    solver_time_limit_seconds: float = Field(default=60.0, ge=1.0, le=MAX_SOLVER_TIME_LIMIT_SECONDS)
    solver_workers: int | None = Field(default=None, ge=1, le=32)
    generation_mode: str = DEFAULT_GENERATION_MODE
    max_auto_stage: str | None = None
    skip_diversity: bool = False


@router.post("/v3/generate")
async def generate_v3(request: GenerateV3Request):
    """Run full V3 pipeline: placement → templates → CP-SAT global selection.

    Professional courses only (pre-filtered teaching tasks required).
    """
    try:
        return run_v3_pipeline(
            allocation_task_id=request.allocation_task_id,
            top_k=request.top_k,
            plan_count=request.plan_count,
            scheme_count=request.scheme_count,
            solver_time_limit_seconds=request.solver_time_limit_seconds,
            solver_workers=request.solver_workers,
            generation_mode=request.generation_mode,
            max_auto_stage=request.max_auto_stage,
            skip_diversity=request.skip_diversity,
            output_dir=request.output_dir,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate-scheme", status_code=202)
async def submit_generate_scheme(request: GenerateSchemeRequest):
    """Java-compatible async generation endpoint backed by the V3 pipeline."""

    task_uid = uuid.uuid4().hex[:12]
    _tasks[task_uid] = {"status": "running", "result": None, "error": None}
    _events[task_uid] = []
    _event_queues[task_uid] = []

    def _push(event: str, data: dict):
        msg = {"event": event, "data": data}
        _events[task_uid].append(msg)
        for queue in list(_event_queues.get(task_uid, [])):
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _run():
        try:
            _push("progress", {"message": "开始 V3 CP-SAT 排课"})
            result = run_v3_pipeline(
                allocation_task_id=request.task_id,
                top_k=request.top_k,
                plan_count=request.plan_count,
                scheme_count=request.scheme_count,
                solver_time_limit_seconds=request.solver_time_limit_seconds,
                solver_workers=request.solver_workers,
                generation_mode=request.generation_mode,
                max_auto_stage=request.max_auto_stage,
                skip_diversity=request.skip_diversity,
                progress_callback=lambda payload: _push("progress", payload),
            )
            _tasks[task_uid] = {"status": "completed", "result": result, "error": None}
            _push("completed", result)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            _tasks[task_uid] = {"status": "failed", "result": None, "error": error}
            _push("failed", {"error": error})

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task_uid, "status_url": f"/api/ml/generate-scheme/{task_uid}"}


@router.get("/generate-scheme/{task_uid}/stream")
async def stream_generate_scheme(task_uid: str):
    if task_uid not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_queues[task_uid].append(queue)

    async def _generate():
        try:
            for msg in _events.get(task_uid, []):
                yield _sse(msg)
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=10)
                    yield _sse(msg)
                    if msg["event"] in {"completed", "failed"}:
                        return
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: \n\n"
                    info = _tasks.get(task_uid)
                    if info and info["status"] in {"completed", "failed"}:
                        return
        finally:
            if queue in _event_queues.get(task_uid, []):
                _event_queues[task_uid].remove(queue)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(msg: dict) -> str:
    return f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False, default=str)}\n\n"
