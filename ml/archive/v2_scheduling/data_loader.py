"""Load scheduling context from the project database."""

from __future__ import annotations

from typing import Any

from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    fetch_allocation_task,
    fetch_classrooms,
    fetch_generation_config,
    fetch_task_teaching_task_ids,
    fetch_tasks,
    fetch_teacher_profiles,
    fetch_time_slots,
)
from ml.scheduling.scoring import build_scoring_config
from ml.scheduling.teacher_profiles import normalize_profiles
from ml.scheduling_v2.models import ScheduleContext, SchedTask, TimeSlotRef

EXCLUDED_COURSE_KEYWORDS = (
    "军事技能",
    "校企合作",
    "综合实训",
    "综合训练",
    "实训",
)


def load_context(task_id: int, teacher_profiles: dict[int, dict[str, Any]] | None = None) -> ScheduleContext:
    db = load_db_config()
    with connect(db) as conn:
        allocation_task = fetch_allocation_task(conn, task_id)
        if not allocation_task:
            raise ValueError(f"task {task_id} not found")
        teaching_task_ids = set(fetch_task_teaching_task_ids(conn, task_id))
        raw_config = fetch_generation_config(conn, task_id)
        tasks = fetch_tasks(conn)
        classrooms = fetch_classrooms(conn)
        time_slots = fetch_time_slots(conn)
        db_profiles = fetch_teacher_profiles(conn)

    if not teaching_task_ids:
        raise ValueError(f"allocation task {task_id} has no teaching tasks")

    normalized_profiles = normalize_profiles(teacher_profiles or db_profiles)
    filtered_time_slots = _filter_time_slots(time_slots, raw_config)
    if not filtered_time_slots:
        raise ValueError("排课失败：生成配置过滤后没有可用时间段")

    selected_tasks = [
        _to_sched_task(row, normalized_profiles)
        for row in tasks
        if int(row.get("teaching_task_id") or 0) in teaching_task_ids
        and not is_excluded_course(row)
    ]
    if not selected_tasks:
        raise ValueError(f"allocation task {task_id} has no active schedulable teaching tasks")

    slot_by_coord = {
        (
            int(slot["week_number"]),
            int(slot["day_of_week"]),
            int(slot["period_index"]),
        ): TimeSlotRef(
            id=int(slot["id"]),
            week_number=int(slot["week_number"]),
            day_of_week=int(slot["day_of_week"]),
            period_index=int(slot["period_index"]),
        )
        for slot in filtered_time_slots
    }

    return ScheduleContext(
        task_id=task_id,
        task_name=str(allocation_task.get("name") or f"排课任务{task_id}"),
        raw_config=raw_config,
        scoring_config=build_scoring_config(raw_config),
        tasks=tuple(selected_tasks),
        classrooms=tuple(classrooms),
        time_slots=tuple(filtered_time_slots),
        slot_by_coord=slot_by_coord,
        allowed_time_slot_ids=frozenset(slot.id for slot in slot_by_coord.values()),
    )


def is_excluded_course(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("course_name", "course_code", "course_type", "required_room_type")
    )
    return any(keyword in text for keyword in EXCLUDED_COURSE_KEYWORDS)


def resolve_scheme_count(raw_config: dict[str, Any] | None) -> int:
    if not raw_config:
        return 1
    try:
        value = int(raw_config.get("scheme_count") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 5))


def _filter_time_slots(time_slots: list[dict[str, Any]], raw_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not raw_config:
        return list(time_slots)
    allowed_weeks = _parse_int_set(raw_config.get("allowed_weeks"))
    allowed_days = _parse_int_set(raw_config.get("allowed_weekdays"))
    allowed_periods = _parse_int_set(raw_config.get("allowed_periods"))

    result = list(time_slots)
    if allowed_weeks:
        result = [slot for slot in result if int(slot["week_number"]) in allowed_weeks]
    if allowed_days:
        result = [slot for slot in result if int(slot["day_of_week"]) in allowed_days]
    if allowed_periods:
        result = [slot for slot in result if int(slot["period_index"]) in allowed_periods]
    return result


def _to_sched_task(row: dict[str, Any], profiles: dict[int, dict[str, Any]]) -> SchedTask:
    teaching_task_id = int(row.get("teaching_task_id") or 0)
    teacher_id = int(row.get("teacher_id") or 0)
    total_hours = int(row.get("total_hours") or 0)
    total_lessons = total_hours // 2
    return SchedTask(
        teaching_task_id=teaching_task_id,
        teacher_id=teacher_id,
        teacher_name=str(row.get("teacher_name") or ""),
        total_hours=total_hours,
        total_lessons=total_lessons,
        total_student_count=int(row.get("total_student_count") or 0),
        required_room_type=str(row.get("required_room_type") or ""),
        class_group_ids=_parse_id_tuple(row.get("class_group_ids")),
        raw=row,
        teacher_profile=profiles.get(teacher_id),
    )


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
            continue
    return result or None


def _parse_id_tuple(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        parts = value
    else:
        parts = str(value).strip().strip("[]").replace(" ", "").split(",")
    ids: list[int] = []
    for part in parts:
        try:
            parsed = int(part)
        except (TypeError, ValueError):
            continue
        if parsed > 0 and parsed not in ids:
            ids.append(parsed)
    return tuple(ids)
