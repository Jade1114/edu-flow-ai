"""V3 scheduling pipeline orchestrator.

Full pipeline for professional courses only (no public courses):
  1. Fetch teaching tasks from DB
  2. Placement Model → TopK resources per task (parallel)
  3. Template Generator → week distribution plans per task (parallel)
  4. CP-SAT Global Plan Selector → choose one plan per task
  5. Write final schedule JSONL
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    ensure_default_time_slots,
    fetch_allocation_task,
    fetch_all,
    fetch_generation_config,
    fetch_time_slots,
)
from ml.scheduling_v3.cp_sat_selector import (
    DEFAULT_TIME_LIMIT_SECONDS,
    audit_scheme_items,
    select_cp_sat_global_plans_jsonl,
)
from ml.scheduling_v3.placement_direct import DirectPlacementModel
from ml.scheduling_v3.plan_templates import (
    _build_task_plan_row,
    _read_candidate_rows,
    WeekUsageAllocator,
)

DEFAULT_TOP_K = 50
MAX_PLAN_COUNT = 120
DEFAULT_PLAN_COUNT = 120
DEFAULT_SEMESTER_WEEKS = 18
DEFAULT_ALLOWED_WEEKS = set(range(1, DEFAULT_SEMESTER_WEEKS + 1))
DEFAULT_ALLOWED_WEEKDAYS = set(range(1, 6))
DEFAULT_ALLOWED_PERIODS = set(range(1, 6))
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "data" / "generated" / "v3"


def run_v3_pipeline(
    allocation_task_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    plan_count: int = DEFAULT_PLAN_COUNT,
    scheme_count: int | None = None,
    solver_time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run the full V3 scheduling pipeline for professional courses.

    Returns a summary dict with paths and statistics.
    """
    started = time.perf_counter()

    top_k = max(1, min(int(top_k), 50))
    plan_count = max(1, min(int(plan_count), MAX_PLAN_COUNT))

    out_dir = _resolve_output_dir(allocation_task_id, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Load data from DB ───────────────────────────────────
    print("[V3] Step 1: Loading data from DB...")
    db = load_db_config()
    conn = connect(db)
    try:
        allocation_task = fetch_allocation_task(conn, allocation_task_id)
        if not allocation_task:
            raise ValueError(f"Allocation task {allocation_task_id} not found")
        raw_config = fetch_generation_config(conn, allocation_task_id)
        time_slots = fetch_time_slots(conn)
        seeded_time_slots = 0
        if not time_slots:
            seeded_time_slots = ensure_default_time_slots(conn)
            time_slots = fetch_time_slots(conn)
        filtered_time_slots = _filter_time_slots(time_slots, raw_config)
        if not filtered_time_slots:
            raise ValueError(
                "排课失败：生成配置过滤后没有可用时间段，"
                f"time_slot_count={len(time_slots)}, raw_config={raw_config}"
            )
        time_slot_id_by_coord = _time_slot_id_by_coord(filtered_time_slots)
        resolved_scheme_count = scheme_count if scheme_count is not None else _resolve_scheme_count(raw_config)

        teaching_tasks = list(fetch_all(conn,
            """SELECT tt.*, c.code AS course_code, c.name AS course_name,
                      c.course_type, c.required_room_type,
                      t.name AS teacher_name, t.department AS teacher_department
               FROM teaching_task tt
               JOIN allocation_task_teaching_task att ON tt.id = att.teaching_task_id
               JOIN course c ON tt.course_id = c.id
               JOIN teacher t ON tt.primary_teacher_id = t.id
               WHERE att.allocation_task_id = %s""",
            (allocation_task_id,)))
        courses = {c["code"]: c for c in fetch_all(conn, "SELECT * FROM course")}
        classrooms = {c["name"]: c for c in fetch_all(conn, "SELECT * FROM classroom")}
        # Add synthetic IDs for classrooms that don't have them
        for name, room in classrooms.items():
            if not room.get("id"):
                room["id"] = hash(name) % 100000 + 1
        class_groups = {c["name"]: c for c in fetch_all(conn, "SELECT * FROM class_group")}
        teachers = {t["name"]: t for t in fetch_all(conn, "SELECT * FROM teacher")}

        # Load task → class_group mapping
        task_cg_map: dict[int, str] = {}
        cg_rows = fetch_all(conn,
            """SELECT ttcg.teaching_task_id, cg.name AS class_group_name
               FROM teaching_task_class_group ttcg
               JOIN class_group cg ON ttcg.class_group_id = cg.id
               JOIN allocation_task_teaching_task att ON ttcg.teaching_task_id = att.teaching_task_id
               WHERE att.allocation_task_id = %s""",
            (allocation_task_id,))
        for row in cg_rows:
            task_cg_map[row["teaching_task_id"]] = row["class_group_name"]
    finally:
        conn.close()

    print(f"  Tasks: {len(teaching_tasks)}, Courses: {len(courses)}, "
          f"Classrooms: {len(classrooms)}, Classes: {len(class_groups)}, "
          f"Teachers: {len(teachers)}, TimeSlots: {len(time_slot_id_by_coord)}, "
          f"Schemes: {resolved_scheme_count}, SeededTimeSlots: {seeded_time_slots}")

    # ── Step 2: Placement Model inference ───────────────────────────
    print("[V3] Step 2: Placement Model inference...")
    model = DirectPlacementModel.load()
    candidates_path = out_dir / "placement_candidates.jsonl"
    task_count = _run_placement_inference(
        teaching_tasks=teaching_tasks,
        task_cg_map=task_cg_map,
        courses=courses,
        classrooms=classrooms,
        class_groups=class_groups,
        teachers=teachers,
        model=model,
        top_k=top_k,
        output_path=candidates_path,
        allocation_task_id=allocation_task_id,
        raw_config=raw_config,
    )
    print(f"  {task_count} tasks → {candidates_path}")

    # ── Step 3: Template generation ─────────────────────────────────
    print("[V3] Step 3: Template generation...")
    task_plans_path = out_dir / "task_plans.jsonl"
    task_plans_count = _run_template_generation_parallel(
        candidates_path=str(candidates_path),
        output_path=task_plans_path,
        plan_count=plan_count,
    )
    print(f"  {task_plans_count} tasks → {task_plans_path}")

    # ── Step 4: CP-SAT global plan selection ─────────────────────────
    print("[V3] Step 4: CP-SAT global plan selection...")
    cp_sat_summary = select_cp_sat_global_plans_jsonl(
        task_plans_path,
        time_slot_id_by_coord=time_slot_id_by_coord,
        scheme_count=resolved_scheme_count,
        time_limit_seconds=solver_time_limit_seconds,
        output_dir=out_dir,
    )
    schemes_path = Path(cp_sat_summary["output_path"])
    conflicts_after = _audit_schemes_jsonl(schemes_path)
    print(f"  Schemes: {cp_sat_summary['scheme_count']}/{resolved_scheme_count}; "
          f"Conflicts after: {conflicts_after}")

    runtime_s = round(time.perf_counter() - started, 2)
    summary = {
        "architecture": "v3_cp_sat_global_plan_selector",
        "allocation_task_id": allocation_task_id,
        "output_dir": str(out_dir),
        "schemes_path": str(schemes_path),
        "candidates_path": str(candidates_path),
        "task_plans_path": str(task_plans_path),
        "cp_sat_summary_path": cp_sat_summary.get("summary_path"),
        "task_count": len(teaching_tasks),
        "assigned_count": cp_sat_summary.get("task_count"),
        "placement_top_k": top_k,
        "plan_count": plan_count,
        "scheme_count": cp_sat_summary.get("scheme_count"),
        "scheme_count_requested": resolved_scheme_count,
        "solver_status": cp_sat_summary.get("solver_status"),
        "seeded_time_slots": seeded_time_slots,
        "conflicts": conflicts_after,
        "runtime_s": runtime_s,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    summary_path = out_dir / "v3_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print(f"[V3] Done in {runtime_s}s. Conflicts: {conflicts_after}")
    print(f"  → {schemes_path}")
    return summary


# ── internal helpers ──────────────────────────────────────────────────

def _resolve_output_dir(allocation_task_id: int, output_dir: Path | str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
    return OUTPUT_ROOT / f"task_{allocation_task_id}_{ts}"


def _run_placement_inference(
    *,
    teaching_tasks: list[dict],
    task_cg_map: dict[int, str],
    courses: dict[str, dict],
    classrooms: dict[str, dict],
    class_groups: dict[str, dict],
    teachers: dict[str, dict],
    model: DirectPlacementModel,
    top_k: int,
    output_path: Path,
    allocation_task_id: int,
    raw_config: dict[str, Any] | None,
) -> int:
    """Run model inference on all tasks in parallel, write placement candidates JSONL."""
    workers = min(8, max(1, (os.cpu_count() or 4) - 1))

    def _infer_one(task: dict) -> str | None:
        row = _build_candidate_row(
            task=task,
            task_cg_map=task_cg_map,
            courses=courses,
            classrooms=classrooms,
            class_groups=class_groups,
            teachers=teachers,
            model=model,
            top_k=top_k,
            allocation_task_id=allocation_task_id,
            raw_config=raw_config,
        )
        if row is None:
            return None
        return json.dumps(row, ensure_ascii=False, default=str)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_infer_one, t): t for t in teaching_tasks}
            for future in as_completed(futures):
                line = future.result()
                if line is not None:
                    f.write(line + "\n")
                    count += 1
    return count


def _run_template_generation_parallel(
    *,
    candidates_path: str,
    output_path: Path,
    plan_count: int,
) -> int:
    """Generate task plans in parallel using multiple threads.

    Each thread has its own WeekUsageAllocator to avoid contention.
    """
    workers = min(8, max(1, (os.cpu_count() or 4) - 1))
    candidate_rows = _read_candidate_rows(Path(candidates_path))
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def _gen_one(candidate_row: dict) -> str | None:
        allocator = WeekUsageAllocator()
        try:
            row = _build_task_plan_row(
                candidate_row,
                plan_count=plan_count,
                generated_at=generated_at,
                allocator=allocator,
            )
        except Exception:
            return None
        return json.dumps(row, ensure_ascii=False, default=str)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_gen_one, row): idx
                for idx, (_, row) in enumerate(candidate_rows)
            }
            for future in as_completed(futures):
                line = future.result()
                if line is not None:
                    f.write(line + "\n")
                    count += 1
    return count


def _build_candidate_row(
    *,
    task: dict,
    task_cg_map: dict[int, str],
    courses: dict[str, dict],
    classrooms: dict[str, dict],
    class_groups: dict[str, dict],
    teachers: dict[str, dict],
    model: DirectPlacementModel,
    top_k: int,
    allocation_task_id: int,
    raw_config: dict[str, Any] | None,
) -> dict | None:
    """Build one placement candidate row for a teaching task."""
    tid = task.get("id")
    course_code = (task.get("course_code") or "").strip()
    teacher_name = (task.get("teacher_name") or "").strip()
    class_name = (task_cg_map.get(tid) or task.get("class_group") or "").strip()

    course = courses.get(course_code, {})
    cg = class_groups.get(class_name, {})
    teacher = teachers.get(teacher_name, {})

    if not course_code or not class_name:
        return None
    allowed_day_periods = _allowed_day_periods(raw_config)

    # Build feature dict for the model
    row_dict = {
        "course_name": course.get("name", ""),
        "course_code": course_code,
        "teacher_no": teacher.get("no", teacher.get("teacher_no", "")),
        "teacher_name": teacher_name,
        "class_name": class_name,
        "class_major": cg.get("major", ""),
        "class_department": cg.get("department", ""),
        "class_grade": str(cg.get("grade", "")),
        "student_count": str(task.get("student_count") or cg.get("student_count") or 0),
        "total_hours": str(task.get("total_hours") or course.get("hours") or 0),
        "course_type": course.get("course_type", ""),
        "required_room_type": course.get("required_room_type", ""),
    }

    try:
        predictions = model.predict_topk(row_dict, top_k=top_k)
    except Exception:
        return None

    resources = []
    seen_resource_keys: set[str] = set()
    for resource_key, score in predictions:
        parsed = _parse_resource_key(resource_key)
        if parsed is None:
            continue
        classroom_name, day_of_week, period_index = parsed
        if (day_of_week, period_index) not in allowed_day_periods:
            continue
        room = classrooms.get(classroom_name, {})
        if resource_key in seen_resource_keys:
            continue
        seen_resource_keys.add(resource_key)
        resources.append({
            "resource_key": resource_key,
            "slot": {
                "day_of_week": day_of_week,
                "period_index": period_index,
            },
            "classroom": {
                "id": room.get("id"),
                "name": classroom_name,
                "classroom_type": room.get("classroom_type", ""),
            },
            "score": round(score, 6),
        })

    _append_day_period_fallback_resources(
        resources=resources,
        seen_resource_keys=seen_resource_keys,
        allowed_day_periods=allowed_day_periods,
        classrooms=classrooms,
        required_room_type=str(course.get("required_room_type") or ""),
        student_count=int(task.get("student_count") or cg.get("student_count") or 0),
        teaching_task_id=int(tid or 0),
    )
    resources = _prioritize_day_period_coverage(resources, allowed_day_periods)

    if not resources:
        return None

    total_hours = int(float(task.get("total_hours") or course.get("hours") or 0))
    total_sessions = int(task.get("total_sessions") or total_hours // 2)

    return {
        "allocation_task_id": allocation_task_id,
        "teaching_task_id": task.get("id"),
        "input": row_dict,
        "task": {
            "teaching_task_id": task.get("id"),
            "teacher_name": teacher_name,
            "teacher_id": teacher.get("id"),
            "class_group_name": class_name,
            "class_group_ids": [cg.get("id")] if cg.get("id") else [],
            "total_hours": total_hours,
            "total_sessions": total_sessions,
            "course_code": course_code,
            "course_type": course.get("course_type", ""),
        },
        "resources": resources,
        "meta": {
            "source": "v3_placement_direct",
            "model": "lightgbm_multiclass",
            "top_k": top_k,
            "num_classes": len(model.resource_by_label),
            "allowed_weeks": _allowed_weeks(raw_config),
        },
    }


def _append_day_period_fallback_resources(
    *,
    resources: list[dict[str, Any]],
    seen_resource_keys: set[str],
    allowed_day_periods: set[tuple[int, int]],
    classrooms: dict[str, dict],
    required_room_type: str,
    student_count: int,
    teaching_task_id: int,
) -> None:
    room_pool = _fallback_room_pool(classrooms, required_room_type, student_count)
    if not room_pool:
        return
    counts_by_slot: Counter[tuple[int, int]] = Counter()
    for resource in resources:
        slot = resource.get("slot") or {}
        key = (int(slot.get("day_of_week") or 0), int(slot.get("period_index") or 0))
        if key in allowed_day_periods:
            counts_by_slot[key] += 1

    minimum_alternatives_per_slot = min(3, len(room_pool))
    for day, period in sorted(allowed_day_periods):
        offset = 0
        while counts_by_slot[(day, period)] < minimum_alternatives_per_slot and offset < len(room_pool):
            room = _pick_fallback_room(room_pool, teaching_task_id, day, period, offset=offset)
            offset += 1
            room_name = str(room.get("name") or "")
            if not room_name:
                continue
            resource_key = f"{room_name}|{day}|{period}"
            if resource_key in seen_resource_keys:
                continue
            seen_resource_keys.add(resource_key)
            counts_by_slot[(day, period)] += 1
            resources.append({
                "resource_key": resource_key,
                "slot": {
                    "day_of_week": day,
                    "period_index": period,
                },
                "classroom": {
                    "id": room.get("id"),
                    "name": room_name,
                    "classroom_type": room.get("classroom_type", ""),
                },
                "score": 0.000001,
                "source": "day_period_fallback",
            })


def _prioritize_day_period_coverage(
    resources: list[dict[str, Any]],
    allowed_day_periods: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Spread early plan options across day/periods and room alternatives."""
    by_slot: dict[tuple[int, int], list[dict[str, Any]]] = {key: [] for key in allowed_day_periods}
    for resource in resources:
        slot = resource.get("slot") or {}
        key = (int(slot.get("day_of_week") or 0), int(slot.get("period_index") or 0))
        if key not in allowed_day_periods:
            continue
        by_slot[key].append(resource)

    for slot_resources in by_slot.values():
        slot_resources.sort(
            key=lambda resource: (
                -float(resource.get("score") or 0.0),
                str((resource.get("classroom") or {}).get("name") or ""),
                int((resource.get("classroom") or {}).get("id") or 0),
            )
        )

    ordered: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    max_depth = max((len(slot_resources) for slot_resources in by_slot.values()), default=0)
    for depth in range(max_depth):
        for key in sorted(by_slot):
            slot_resources = by_slot[key]
            if depth >= len(slot_resources):
                continue
            resource = slot_resources[depth]
            if id(resource) in used_ids:
                continue
            ordered.append(resource)
            used_ids.add(id(resource))

    ordered.extend(resource for resource in resources if id(resource) not in used_ids)
    return ordered


def _fallback_room_pool(classrooms: dict[str, dict], required_room_type: str, student_count: int) -> list[dict]:
    required = required_room_type.strip()
    rooms = [
        room
        for room in classrooms.values()
        if int(room.get("capacity") or 0) >= max(0, student_count)
    ]
    if required:
        exact = [room for room in rooms if str(room.get("classroom_type") or "").strip() == required]
        if exact:
            rooms = exact
    return sorted(
        rooms,
        key=lambda room: (
            int(room.get("capacity") or 0),
            int(room.get("id") or 0),
            str(room.get("name") or ""),
        ),
    )


def _pick_fallback_room(room_pool: list[dict], teaching_task_id: int, day: int, period: int, *, offset: int = 0) -> dict:
    index = (teaching_task_id * 31 + day * 7 + period + offset) % len(room_pool)
    return room_pool[index]


def _parse_resource_key(resource_key: str) -> tuple[str, int, int] | None:
    """Parse 'classroom_name|day|period' into components."""
    parts = resource_key.split("|")
    if len(parts) != 3:
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _resolve_scheme_count(raw_config: dict[str, Any] | None) -> int:
    if not raw_config:
        return 1
    try:
        value = int(raw_config.get("scheme_count") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 20))


def _filter_time_slots(time_slots: list[dict[str, Any]], raw_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    allowed_weeks = _parse_int_set(raw_config.get("allowed_weeks") if raw_config else None) or DEFAULT_ALLOWED_WEEKS
    allowed_weekdays = (
        _parse_int_set(raw_config.get("allowed_weekdays") if raw_config else None)
        or DEFAULT_ALLOWED_WEEKDAYS
    )
    allowed_periods = (
        _parse_int_set(raw_config.get("allowed_periods") if raw_config else None)
        or DEFAULT_ALLOWED_PERIODS
    )
    result = []
    for slot in time_slots:
        week = int(slot.get("week_number") or 0)
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        if week not in allowed_weeks:
            continue
        if day not in allowed_weekdays:
            continue
        if period not in allowed_periods:
            continue
        result.append(slot)
    return result


def _time_slot_id_by_coord(time_slots: list[dict[str, Any]]) -> dict[tuple[int, int, int], int]:
    return {
        (int(slot["week_number"]), int(slot["day_of_week"]), int(slot["period_index"])): int(slot["id"])
        for slot in time_slots
    }


def _allowed_day_periods(raw_config: dict[str, Any] | None) -> set[tuple[int, int]]:
    allowed_days = (
        _parse_int_set(raw_config.get("allowed_weekdays") if raw_config else None)
        or DEFAULT_ALLOWED_WEEKDAYS
    )
    allowed_periods = (
        _parse_int_set(raw_config.get("allowed_periods") if raw_config else None)
        or DEFAULT_ALLOWED_PERIODS
    )
    days = sorted(allowed_days)
    periods = sorted(allowed_periods)
    return {(day, period) for day in days for period in periods}


def _allowed_weeks(raw_config: dict[str, Any] | None) -> list[int]:
    allowed = _parse_int_set(raw_config.get("allowed_weeks") if raw_config else None) or DEFAULT_ALLOWED_WEEKS
    return sorted(allowed)


def _parse_int_set(value: Any) -> set[int] | None:
    if value is None:
        return None
    raw = str(value).strip().strip("[]").replace(" ", "")
    if not raw:
        return None
    result: set[int] = set()
    for part in raw.split(","):
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            pass
    return result or None


def _audit_schemes_jsonl(path: Path) -> dict[str, int]:
    total = {"teacher": 0, "class": 0, "room": 0, "time_slot_mapping": 0, "hour_mismatch": 0}
    for scheme in _read_jsonl(path):
        conflicts = audit_scheme_items(list(scheme.get("items") or []))
        for key, value in conflicts.items():
            total[key] = total.get(key, 0) + int(value)
    return total
