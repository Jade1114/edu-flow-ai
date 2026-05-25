"""GA 排课 API 端点 — SSE 推送状态"""

from __future__ import annotations
import asyncio, json, threading, uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["ga"])

_tasks: dict[str, dict[str, Any]] = {}
_events: dict[str, list[dict[str, Any]]] = {}
_event_queues: dict[str, list[asyncio.Queue]] = {}


class GenerateRequest(BaseModel):
    task_id: int
    teacher_profiles_jsonl: str | None = None


@router.post("/generate-scheme", status_code=202)
async def submit(req: GenerateRequest):
    task_uid = uuid.uuid4().hex[:12]
    _tasks[task_uid] = {"status": "running", "result": None, "error": None}
    _events[task_uid] = []
    _event_queues[task_uid] = []

    def _push(event: str, data: dict):
        msg = {"event": event, "data": data}
        _events[task_uid].append(msg)
        for q in _event_queues[task_uid]:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _run():
        try:
            _push("progress", {"message": "开始排课"})
            from ml.scripts.generate_scheme_ga import run
            result = run(req.task_id, teacher_profiles_jsonl=req.teacher_profiles_jsonl)
            _tasks[task_uid] = {"status": "completed", "result": result, "error": None}
            _push("completed", result)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            _tasks[task_uid] = {"status": "failed", "result": None, "error": err}
            _push("failed", {"error": err})

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task_uid, "status_url": f"/api/ml/generate-scheme/{task_uid}"}


@router.get("/generate-scheme/{task_uid}/stream")
async def stream(task_uid: str, request: Request):
    if task_uid not in _tasks:
        raise HTTPException(404, "task not found")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_queues[task_uid].append(queue)

    async def _generate():
        try:
            # 把已有的 events 先发出去
            for msg in _events[task_uid]:
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False, default=str)}\n\n"

            # 等新事件
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=10)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False, default=str)}\n\n"
                    if msg["event"] in ("completed", "failed"):
                        return
                except asyncio.TimeoutError:
                    # 心跳，保持连接
                    yield f"event: heartbeat\ndata: \n\n"
                    # 检查是否已结束
                    info = _tasks.get(task_uid)
                    if info and info["status"] in ("completed", "failed"):
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
