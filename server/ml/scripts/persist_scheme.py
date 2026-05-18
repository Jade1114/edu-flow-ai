"""Persist GA-generated schemes + conflict detection directly to MySQL.

Replaces Java's AllocationSchemeGenerationService + ConflictDetector.
Called from run_ga_pipeline_by_task() after GA completes.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from generate_training_samples import fetch_all

# ── Constants ──────────────────────────────────────────────────────────

CONFLICT_TEACHER = "TEACHER_TIME"
CONFLICT_CLASS = "CLASS_GROUP_TIME"
CONFLICT_CLASSROOM = "CLASSROOM_TIME"
CONFLICT_WORKLOAD = "TEACHER_WORKLOAD"

STATUS_CANDIDATE = "CANDIDATE"
STATUS_REJECTED = "REJECTED"
BIZ_TYPE = "ALLOCATION_ITEM"


# ── Conflict Detection ────────────────────────────────────────────────

def detect_conflicts(
    items: list[dict[str, Any]],
    connection: Any,
) -> list[dict[str, Any]]:
    """Detect teacher/class/classroom time + workload conflicts.

    Ported from Java AllocationSchemeConflictDetector.detect().
    """
    if not items:
        return []

    # Preload teaching task details
    task_ids = list({item["teaching_task_id"] for item in items})
    task_map = _load_task_details(connection, task_ids)
    week_map = _load_week_map(connection)

    violations: list[dict[str, Any]] = []

    # 1. Teacher time conflicts
    _detect_group(items, lambda item: (task_map.get(item["teaching_task_id"], {}).get("teacher_id"), item["time_slot_id"]),
                  lambda item, group: _teacher_violation(item, group, task_map),
                  violations)

    # 2. Class group time conflicts
    _detect_group(items, lambda item: _class_key(item, task_map),
                  lambda item, group: _class_violation(item, group, task_map),
                  violations)

    # 3. Classroom time conflicts
    _detect_group(items, lambda item: (item.get("classroom_id"), item["time_slot_id"]),
                  lambda item, group: _room_violation(item, group),
                  violations)

    # 4. Workload violations
    _detect_workload(items, task_map, week_map, violations)

    return violations


def summarize_violations(violations: list[dict[str, Any]]) -> str:
    if not violations:
        return "无明显冲突"
    counts: dict[str, int] = {}
    for v in violations:
        counts[v["conflict_type"]] = counts.get(v["conflict_type"], 0) + 1
    parts = []
    _append_summary(parts, counts, CONFLICT_TEACHER, "教师时间冲突")
    _append_summary(parts, counts, CONFLICT_CLASS, "班级时间冲突")
    _append_summary(parts, counts, CONFLICT_CLASSROOM, "教室时间冲突")
    _append_summary(parts, counts, CONFLICT_WORKLOAD, "教师工作量冲突")
    return f"发现 {len(violations)} 条冲突记录：" + "，".join(parts)


def _detect_group(
    items: list[dict[str, Any]],
    key_fn: Any,
    violation_fn: Any,
    violations: list,
) -> None:
    groups: dict = {}
    for item in items:
        key = key_fn(item)
        if key is None or key[0] is None:
            continue
        groups.setdefault(key, []).append(item)
    for group in groups.values():
        if len(group) > 1:
            for item in group:
                violations.append(violation_fn(item, group))


def _teacher_violation(item: dict, group: list, task_map: dict) -> dict:
    tid = item["teaching_task_id"]
    teacher_name = task_map.get(tid, {}).get("teacher_name", f"教师{task_map.get(tid, {}).get('teacher_id')}")
    return {
        "item_id": item.get("id"),
        "conflict_type": CONFLICT_TEACHER,
        "message": f"教师时间冲突：{teacher_name} 在时间段ID {item['time_slot_id']} 被重复安排",
        "teacher_id": task_map.get(tid, {}).get("teacher_id"),
        "class_group_id": None,
        "classroom_id": None,
        "time_slot_id": item["time_slot_id"],
    }


def _class_key(item: dict, task_map: dict) -> Optional[tuple]:
    class_ids = task_map.get(item["teaching_task_id"], {}).get("class_group_ids")
    if not class_ids:
        return None
    return (class_ids[0], item["time_slot_id"])


def _class_violation(item: dict, group: list, task_map: dict) -> dict:
    tid = item["teaching_task_id"]
    class_names = task_map.get(tid, {}).get("class_group_names", "班级")
    return {
        "item_id": item.get("id"),
        "conflict_type": CONFLICT_CLASS,
        "message": f"班级时间冲突：{class_names} 在时间段ID {item['time_slot_id']} 被重复安排",
        "teacher_id": None,
        "class_group_id": class_names,
        "classroom_id": None,
        "time_slot_id": item["time_slot_id"],
    }


def _room_violation(item: dict, group: list) -> dict:
    return {
        "item_id": item.get("id"),
        "conflict_type": CONFLICT_CLASSROOM,
        "message": f"教室时间冲突：教室ID {item['classroom_id']} 在时间段ID {item['time_slot_id']} 被重复占用",
        "teacher_id": None,
        "class_group_id": None,
        "classroom_id": item["classroom_id"],
        "time_slot_id": item["time_slot_id"],
    }


def _detect_workload(
    items: list[dict],
    task_map: dict,
    week_map: dict[int, int],
    violations: list,
) -> None:
    groups: dict = {}
    for item in items:
        detail = task_map.get(item["teaching_task_id"])
        if not detail or not detail.get("teacher_id"):
            continue
        week = week_map.get(item["time_slot_id"])
        if week is None:
            continue
        key = f"{detail['teacher_id']}:{week}"
        groups.setdefault(key, []).append(item)

    for key, group in groups.items():
        first = group[0]
        detail = task_map.get(first["teaching_task_id"])
        if not detail:
            continue
        max_hours = detail.get("max_weekly_hours")
        if max_hours is None:
            continue
        total_hours = len(group) * 2
        if total_hours <= max_hours:
            continue

        teacher_id_str, week_str = key.split(":")
        week_num = int(week_str)
        for item in group:
            violations.append({
                "item_id": item.get("id"),
                "conflict_type": CONFLICT_WORKLOAD,
                "message": f"教师工作量冲突：{detail['teacher_name']} 第 {week_num} 周共 {total_hours} 课时，"
                           f"超过最大周课时 {max_hours} 课时",
                "teacher_id": detail["teacher_id"],
                "class_group_id": None,
                "classroom_id": None,
                "time_slot_id": item["time_slot_id"],
            })


def _load_task_details(connection, task_ids: list[int]) -> dict:
    """Load teaching task details needed for conflict detection."""
    if not task_ids:
        return {}
    placeholders = ",".join("%s" for _ in task_ids)
    rows = fetch_all(
        connection,
        f"""
        SELECT tt.id, tt.primary_teacher_id, t.name AS teacher_name,
               t.max_weekly_hours,
               GROUP_CONCAT(DISTINCT cg.id ORDER BY cg.id) AS class_group_ids,
               GROUP_CONCAT(DISTINCT cg.name ORDER BY cg.id) AS class_group_names
        FROM teaching_task tt
        JOIN teacher t ON t.id = tt.primary_teacher_id
        LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
        LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
        WHERE tt.id IN ({placeholders})
        GROUP BY tt.id, tt.primary_teacher_id, t.name, t.max_weekly_hours
        """,
        task_ids,
    )
    result: dict = {}
    for row in rows:
        tid = int(row["id"])
        cg_ids = row.get("class_group_ids")
        cg_names = row.get("class_group_names")
        result[tid] = {
            "teacher_id": int(row["primary_teacher_id"]),
            "teacher_name": row["teacher_name"],
            "max_weekly_hours": int(row["max_weekly_hours"]) if row.get("max_weekly_hours") else None,
            "class_group_ids": [int(x) for x in cg_ids.split(",")] if cg_ids else [],
            "class_group_names": cg_names.split(",") if cg_names else [],
        }
    return result


def _load_week_map(connection) -> dict[int, int]:
    rows = fetch_all(connection, "SELECT id, week_number FROM time_slot")
    return {int(row["id"]): int(row["week_number"]) for row in rows}


def _append_summary(parts: list, counts: dict, ctype: str, label: str) -> None:
    count = counts.get(ctype, 0)
    if count:
        parts.append(f"{label} {count} 条")


# ── Persistence ───────────────────────────────────────────────────────

def _db_text(value: Any) -> Any:
    """Convert structured values to DB-safe TEXT payloads."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def reject_old_candidates(connection, task_id: int) -> None:
    """Mark existing CANDIDATE schemes as REJECTED."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE allocation_scheme SET status = %s WHERE task_id = %s AND status = %s",
            (STATUS_REJECTED, task_id, STATUS_CANDIDATE),
        )


def insert_scheme(connection, task_id: int, scheme_data: dict) -> int:
    """Insert a scheme row and return its id."""
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO allocation_scheme
               (task_id, scheme_name, summary, scheme_score, evaluation_summary,
                policy, model_version, conflict_summary, valid, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                task_id,
                scheme_data.get("scheme_name", ""),
                _db_text(scheme_data.get("summary")),
                scheme_data.get("scheme_score"),
                _db_text(scheme_data.get("evaluation_summary")),
                scheme_data.get("policy"),
                scheme_data.get("model_version"),
                _db_text(scheme_data.get("conflict_summary")),
                scheme_data.get("valid", True),
                STATUS_CANDIDATE,
            ),
        )
        return int(cursor.lastrowid)


def insert_item(connection, scheme_id: int, item_data: dict) -> int:
    """Insert an allocation item and return its id."""
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO allocation_item
               (scheme_id, teaching_task_id, classroom_id, time_slot_id, valid, conflict_message)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                scheme_id,
                item_data["teaching_task_id"],
                item_data["classroom_id"],
                item_data["time_slot_id"],
                item_data.get("valid", True),
                item_data.get("conflict_message"),
            ),
        )
        return int(cursor.lastrowid)


def insert_conflict(connection, violation: dict) -> None:
    """Insert conflict check result."""
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO conflict_check_result
               (biz_type, biz_id, conflict_type, message,
                related_teacher_id, related_classroom_id, related_time_slot_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                BIZ_TYPE,
                violation.get("item_id"),
                violation["conflict_type"],
                violation["message"],
                violation.get("teacher_id"),
                violation.get("classroom_id"),
                violation.get("time_slot_id"),
            ),
        )


def update_scheme_conflict_state(connection, scheme_id: int, valid: bool, conflict_summary: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE allocation_scheme SET valid = %s, conflict_summary = %s WHERE id = %s",
            (valid, conflict_summary, scheme_id),
        )
