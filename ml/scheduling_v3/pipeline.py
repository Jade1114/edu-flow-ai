"""V3 scheduling pipeline orchestrator.

Full pipeline for professional courses only (no public courses):
  1. Fetch teaching tasks from DB
  2. Placement Model → TopK resources per task (parallel)
  3. Template Generator → week distribution plans per task (parallel)
  4. Teacher Group Solver → resolve within-teacher conflicts
  5. Class Conflict Resolver → resolve cross-group class conflicts
  6. Write final schedule JSONL
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from ml.db.config import connect, load_db_config
from ml.db.repositories import fetch_allocation_task, fetch_all
from ml.scheduling_v3.placement_direct import DirectPlacementModel, direct_features
from ml.scheduling_v3.plan_templates import (
    generate_task_plans_jsonl,
    _build_task_plan_row,
    _read_candidate_rows,
    WeekUsageAllocator,
)
from ml.scheduling_v3.teacher_group_solver import solve_teacher_groups
from ml.scheduling_v3.class_conflict_resolver import resolve_class_conflicts

DEFAULT_TOP_K = 10
DEFAULT_PLAN_COUNT = 8
DEFAULT_SEMESTER_WEEKS = 18
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "data" / "generated" / "v3"


def run_v3_pipeline(
    allocation_task_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    plan_count: int = DEFAULT_PLAN_COUNT,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run the full V3 scheduling pipeline for professional courses.

    Returns a summary dict with paths and statistics.
    """
    started = time.perf_counter()

    top_k = max(1, min(int(top_k), 50))
    plan_count = max(1, min(int(plan_count), 50))

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
          f"Teachers: {len(teachers)}")

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

    # ── Step 4: Teacher group solver ────────────────────────────────
    print("[V3] Step 4: Teacher group solving...")
    task_plans = _read_jsonl(task_plans_path)
    group_assignments = solve_teacher_groups(
        task_plans=task_plans,
        semester_weeks=DEFAULT_SEMESTER_WEEKS,
    )
    print(f"  {len(group_assignments)} tasks assigned across "
          f"{len(set(a.get('teacher_name') for a in group_assignments))} teacher groups")

    # ── Step 5: Class conflict resolution ───────────────────────────
    print("[V3] Step 5: Class conflict resolution...")
    resolved = resolve_class_conflicts(
        assignments=group_assignments,
        task_plans=task_plans,
        class_groups=class_groups,
    )
    conflicts_after = _count_conflicts(resolved)
    print(f"  Conflicts after: teacher={conflicts_after['teacher']}, "
          f"class={conflicts_after['class']}, room={conflicts_after['room']}")

    # ── Step 6: Write final schedule ────────────────────────────────
    print("[V3] Step 6: Writing final schedule...")
    schemes_path = out_dir / "schemes.jsonl"
    scheme = _build_scheme(resolved)
    with open(schemes_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(scheme, ensure_ascii=False, default=str) + "\n")

    runtime_s = round(time.perf_counter() - started, 2)
    summary = {
        "architecture": "v3_teacher_group_decomposition",
        "allocation_task_id": allocation_task_id,
        "output_dir": str(out_dir),
        "schemes_path": str(schemes_path),
        "candidates_path": str(candidates_path),
        "task_plans_path": str(task_plans_path),
        "task_count": len(teaching_tasks),
        "assigned_count": len(resolved),
        "placement_top_k": top_k,
        "plan_count": plan_count,
        "teacher_groups": len(set(a.get("teacher_name") for a in resolved)),
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
    for resource_key, score in predictions:
        parsed = _parse_resource_key(resource_key)
        if parsed is None:
            continue
        classroom_name, day_of_week, period_index = parsed
        room = classrooms.get(classroom_name, {})
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
        },
    }


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


def _build_scheme(assignments: list[dict]) -> dict:
    """Build final scheme dict from resolved assignments."""
    items = []
    total_score = 0.0
    for a in assignments:
        for item in a.get("items", []):
            items.append(item)
            total_score += float(item.get("placement_score", 0))

    items.sort(key=lambda x: (
        int(x.get("teaching_task_id") or 0),
        int(x.get("week_number") or 0),
        int(x.get("day_of_week") or 0),
        int(x.get("period_index") or 0),
    ))

    conflicts = _count_conflicts(assignments)

    return {
        "scheme_index": 1,
        "items": items,
        "hard_conflicts": conflicts["teacher"] + conflicts["class"] + conflicts["room"],
        "quality_score": round(total_score, 4),
        "conflict_summary": conflicts,
        "assignment_count": len(items),
    }


def _count_conflicts(assignments: list[dict]) -> dict[str, int]:
    """Count teacher, class, and room conflicts in assignments."""
    teacher_slots: dict[tuple[int, int, int, int], int] = {}
    class_slots: dict[tuple[int, int, int, int], int] = {}
    room_slots: dict[tuple[int, int, int, int], int] = {}

    teacher_conflicts = 0
    class_conflicts = 0
    room_conflicts = 0

    for a in assignments:
        for item in a.get("items", []):
            tid = item.get("teacher_id", 0)
            cids = item.get("class_group_ids", [])
            rid = item.get("classroom_id", 0)
            week = item.get("week_number", 0)
            day = item.get("day_of_week", 0)
            period = item.get("period_index", 0)

            if tid and week and day and period:
                key = (tid, week, day, period)
                teacher_slots[key] = teacher_slots.get(key, 0) + 1
                if teacher_slots[key] > 1:
                    teacher_conflicts += 1

            if rid and week and day and period:
                key = (rid, week, day, period)
                room_slots[key] = room_slots.get(key, 0) + 1
                if room_slots[key] > 1:
                    room_conflicts += 1

            for cid in cids:
                if cid and week and day and period:
                    key = (cid, week, day, period)
                    class_slots[key] = class_slots.get(key, 0) + 1
                    if class_slots[key] > 1:
                        class_conflicts += 1

    return {
        "teacher": teacher_conflicts,
        "class": class_conflicts,
        "room": room_conflicts,
    }
