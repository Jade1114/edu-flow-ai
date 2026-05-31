"""GA 排课 API 端点 — SSE 推送状态"""

from __future__ import annotations
import asyncio, json, logging, os, random, sys, threading, uuid
from datetime import datetime as dt
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ml.api.constraint_parser import parse_constraint_text
from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    fetch_tasks, fetch_classrooms, fetch_time_slots,
    fetch_teacher_profiles, fetch_allocation_task,
    fetch_generation_config, fetch_task_teaching_task_ids,
)
from ml.ga_config import resolve_ga_params
from ml.scheduling.pipeline import generate_scheme
from ml.scheduling.scoring import build_scoring_config
from ml.scheduling.infra.constants import PROJECT_LOG_DIR
from ml.scheduling.teacher_profiles import load_teacher_profiles_jsonl
from ml.channels.integration import generate_v2

V2_ENABLED = True  # Toggle V2 engine

router = APIRouter(tags=["ga"])

_tasks: dict[str, dict[str, Any]] = {}
_events: dict[str, list[dict[str, Any]]] = {}
_event_queues: dict[str, list[asyncio.Queue]] = {}


class GenerateRequest(BaseModel):
    task_id: int
    teacher_profiles_jsonl: str | None = None


class TranslateRequest(BaseModel):
    text: str


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
            result = _run_generation(req.task_id, teacher_profiles_jsonl=req.teacher_profiles_jsonl)
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


@router.post("/translate-constraint")
async def translate_constraint(request: TranslateRequest):
    """Translate natural language constraint to structured overrides."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    constraints = parse_constraint_text(request.text)
    return {
        "success": True,
        "constraints": constraints,
        "count": len(constraints),
    }


# ── V2 output writer ─────────────────────────────────
def _write_v2_output(task_id: int, result: dict) -> Path:
    """Write V2 beam search result as scheme files."""
    from datetime import datetime as dt
    ts = dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    out = Path(__file__).resolve().parents[1] / "data" / "generated" / f"task_{task_id}_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    assignments = result.get("assignments", [])
    conflict_info = result.get("conflicts", {})
    stats = result.get("stats", {})

    scheme_data = {
        "items": assignments,
        "v2_engine": True,
        "total_score": result.get("total_score", 0),
        "assign_rate": stats.get("assign_rate", 0),
        "conflict_count": conflict_info.get("conflict_count", 0),
        "conflict_clusters": len(conflict_info.get("conflict_graph", {}).get("clusters", [])),
    }

    (out / "schemes.jsonl").write_text(
        json.dumps(scheme_data, ensure_ascii=False, default=str)
    )
    (out / "ga_summary.json").write_text(json.dumps({
        "v2_engine": True,
        "assignments": len(assignments),
        "total_score": result.get("total_score", 0),
        "assign_rate": stats.get("assign_rate", 0),
        "conflicts": conflict_info.get("conflict_count", 0),
        "unassigned": stats.get("unassigned", 0),
    }, ensure_ascii=False, indent=2))
    _log.info("V2 output: %s assignments → %s", len(assignments), out)
    return out


# ── GA generation (inlined from scripts/generate_scheme_ga.py) ─────

_log = logging.getLogger("ga")


def _setup_logger() -> logging.Logger:
    _log.setLevel(logging.INFO)
    if _log.handlers:
        return _log
    LOG_FILE = PROJECT_LOG_DIR / "ga-algorithm.log"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8", mode="a")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _log.addHandler(handler)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("[GA] %(message)s"))
    _log.addHandler(console)
    return _log


def _run_batch_generation(
    tasks: "list[dict]",
    classrooms: "list[dict]",
    time_slots: "list[dict]",
    teacher_profiles: "dict|None",
    task_id: int,
    raw_config: "dict|None",
    teacher_profiles_jsonl: "str|None",
) -> "dict":
    """Run per-class GA and merge results with conflict detection."""
    from collections import defaultdict

    tasks_by_class: "dict[str, list[dict]]" = defaultdict(list)
    for t in tasks:
        cg = t.get("class_group_names") or t.get("class_group_majors") or "?"
        if isinstance(cg, str) and "," in cg:
            cg = cg.split(",")[0]
        tasks_by_class[cg].append(t)

    _log.info("Batch: %d classes, total %d tasks", len(tasks_by_class), len(tasks))

    ga_params = resolve_ga_params(_log)
    scheme_count = _resolve_scheme_count(raw_config)
    scoring_config = build_scoring_config(raw_config)

    profiles = teacher_profiles
    profile_path = teacher_profiles_jsonl or os.environ.get("TEACHER_PROFILES_JSONL")
    if profile_path:
        profiles = load_teacher_profiles_jsonl(profile_path)

    import random as _random
    class_list = sorted(tasks_by_class.keys())
    all_by_scheme = [{"items": []} for _ in range(scheme_count)]
    all_summaries = []

    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    MAX_WORKERS = min(8, len(class_list))
    
    for si in range(scheme_count):
        _log.info("=== Scheme %d/%d ===", si + 1, scheme_count)
        merged_rows = []
        completed = 0

        def _run_one_class(cg_name, ci):
            cg_tasks = tasks_by_class[cg_name]
            seed = (task_id * 1_000_003 + si * 9_176 + ci * 7919 + 17) % 2_147_483_647
            rng = _random.Random(seed)
            try:
                rows, m = generate_scheme(
                    cg_tasks, classrooms, time_slots, profiles,
                    rng=rng,
                    population_size=int(ga_params["population_size"]),
                    generations=int(ga_params["generations"]),
                    elite_size=int(ga_params["elite_size"]),
                    tournament_size=int(ga_params["tournament_size"]),
                    mutation_rate=float(ga_params["mutation_rate"]),
                    init_candidate_top_n=int(ga_params["candidate_top_n"]),
                    scoring_config=scoring_config,
                )
                return (cg_name, rows, m, None)
            except Exception as e:
                return (cg_name, [], {}, str(e))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(_run_one_class, cg_name, ci): cg_name
                for ci, cg_name in enumerate(class_list)
            }
            for future in as_completed(futures):
                cg_name, rows, m, err = future.result()
                completed += 1
                if err:
                    _log.warning("  [%d/%d] %s FAILED: %s", completed, len(class_list), cg_name, err)
                else:
                    merged_rows.extend(rows)
                    _log.debug("  [%d/%d] %s: %d tasks → quality=%.3f",
                               completed, len(class_list), cg_name,
                               len(rows), m.get("quality_score", 0))

        # Conflict detection
        teacher_slot = defaultdict(list)
        for row in merged_rows:
            slot = (row.get("week_number"), row.get("day_of_week"), row.get("period_index"))
            teacher_slot[(row.get("teaching_task_id"), *slot)].append(row)

        t_conf = sum(1 for v in teacher_slot.values() if len(v) > 1)
        _log.info("  Scheme %d: %d assignments, teacher_conflicts=%d",
                  si + 1, len(merged_rows), t_conf)

        all_by_scheme[si] = {"items": merged_rows}
        all_summaries.append({
            "scheme_index": si + 1, "ga_profile": ga_params.get("profile"),
            "class_count": len(class_list), "total_assignments": len(merged_rows),
            "teacher_conflicts": t_conf,
        })

    ts = dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    out = Path(__file__).resolve().parents[1] / "data" / "generated" / f"task_{task_id}_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemes.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, default=str) for s in all_by_scheme))
    (out / "ga_summary.json").write_text(json.dumps(all_summaries, ensure_ascii=False, indent=2))
    _log.info("Wrote batch results to %s", out)
    return {"output_dir": str(out), "scheme_count": len(all_by_scheme), "timings_ms": {}}


def _run_generation(task_id: int, teacher_profiles_jsonl: str | None = None) -> dict[str, Any]:
    _setup_logger()
    db = load_db_config()
    with connect(db) as conn:
        at = fetch_allocation_task(conn, task_id)
        if not at:
            raise ValueError(f"task {task_id} not found")
        teaching_task_ids = fetch_task_teaching_task_ids(conn, task_id)
        raw_config = fetch_generation_config(conn, task_id)
        tasks = fetch_tasks(conn)
        classrooms = fetch_classrooms(conn)
        time_slots = fetch_time_slots(conn)
        teacher_profiles = fetch_teacher_profiles(conn)

    if raw_config:
        aw = raw_config.get("allowed_weeks", "")
        aw_set = _parse_int_set(str(aw)) if aw else None
        ad = _parse_int_set(str(raw_config.get("allowed_weekdays", "")))
        ap = _parse_int_set(str(raw_config.get("allowed_periods", "")))
        if aw_set:
            time_slots = [s for s in time_slots if int(s["week_number"]) in aw_set]
        if ad:
            time_slots = [s for s in time_slots if int(s["day_of_week"]) in ad]
        if ap:
            time_slots = [s for s in time_slots if int(s["period_index"]) in ap]

    scoring_config = build_scoring_config(raw_config)
    _log.info("Scoring config: early=%s late=%s profile_scale=%s",
                scoring_config.get("early_period_penalty"),
                scoring_config.get("late_period_penalty"),
                scoring_config.get("profile_penalty_scale"))

    tid_set = set(teaching_task_ids)
    tasks = [t for t in tasks if int(t.get("teaching_task_id") or 0) in tid_set]

    # ── V2 engine (Beam Search) or legacy GA batch ──
    if V2_ENABLED:
        _log.info("✅ V2 engine: %d tasks → Beam Search", len(tasks))
        v2_result = generate_v2(tasks, classrooms, time_slots, beam_width=3)
        if v2_result.get("success"):
            # Wrap V2 result into expected scheme format
            out_dir = _write_v2_output(task_id, v2_result)
            return {"output_dir": str(out_dir), "scheme_count": 1, "timings_ms": {}}
        else:
            _log.warning("V2 failed: %s, falling back to GA", v2_result.get("error"))
    
    # Legacy batch GA fallback (split by class_group if tasks > 30)
    BATCH_THRESHOLD = 30
    if len(tasks) > BATCH_THRESHOLD:
        _log.info("Batch mode: %d tasks > %d → splitting by class_group", len(tasks), BATCH_THRESHOLD)
        return _run_batch_generation(tasks, classrooms, time_slots, teacher_profiles,
                                     task_id, raw_config, teacher_profiles_jsonl)
    
    scheme_count = _resolve_scheme_count(raw_config)
    ga_params = resolve_ga_params(_log)
    profile_jsonl_path = teacher_profiles_jsonl or os.environ.get("TEACHER_PROFILES_JSONL")
    if profile_jsonl_path:
        teacher_profiles = load_teacher_profiles_jsonl(profile_jsonl_path)

    schemes = []
    summaries = []
    _log.info(
        "GA effective params for allocation_task_id=%s: profile=%s pop=%s generations=%s elite=%s tournament=%s mutation=%s",
        task_id,
        ga_params.get("profile"),
        ga_params["population_size"],
        ga_params["generations"],
        ga_params["elite_size"],
        ga_params["tournament_size"],
        ga_params["mutation_rate"],
    )
    for index in range(scheme_count):
        _log.info("Generating GA scheme %s/%s for allocation_task_id=%s", index + 1, scheme_count, task_id)
        rng = random.Random((task_id * 1_000_003 + index * 9_176 + 17) % 2_147_483_647)
        rows, metrics = generate_scheme(
            tasks, classrooms, time_slots, teacher_profiles,
            rng=rng,
            population_size=int(ga_params["population_size"]),
            generations=int(ga_params["generations"]),
            elite_size=int(ga_params["elite_size"]),
            tournament_size=int(ga_params["tournament_size"]),
            mutation_rate=float(ga_params["mutation_rate"]),
            init_candidate_top_n=int(ga_params["candidate_top_n"]),
            scoring_config=scoring_config,
        )
        schemes.append({"items": rows})
        summaries.append({"scheme_index": index + 1, "ga_profile": ga_params.get("profile"), **metrics})

    ts = dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    out = Path(__file__).resolve().parents[1] / "data" / "generated" / f"task_{task_id}_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemes.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, default=str) for s in schemes)
    )
    (out / "ga_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
    _log.info("Wrote %s schemes to %s/schemes.jsonl", len(schemes), out)
    return {"output_dir": str(out), "scheme_count": len(schemes), "timings_ms": {}}


def _resolve_scheme_count(raw_config: dict | None) -> int:
    if not raw_config:
        return 1
    try:
        value = int(raw_config.get("scheme_count") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 5))


def _parse_int_set(v: str) -> set[int] | None:
    if not v or not v.strip():
        return None
    v = v.strip().strip("[]").replace(" ", "")
    result = set()
    for part in v.split(","):
        part = part.strip()
        if part:
            try:
                result.add(int(part))
            except ValueError:
                pass
    return result or None
