"""Shared scheduling feature helpers used by sample generation and GA scoring."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PseudoAssignment:
    task_id: int
    teacher_id: int
    class_group_ids: tuple[int, ...]
    classroom_id: int
    time_slot_id: int
    week_number: int
    day_of_week: int
    period_index: int


def parse_id_tuple(raw_ids: str | None) -> tuple[int, ...]:
    if not raw_ids:
        return ()
    return tuple(int(value) for value in raw_ids.split(",") if value)


def effective_required_room_type(task: dict[str, Any]) -> str:
    return task.get("required_room_type") or ""


def periods_needed(task: dict[str, Any]) -> int:
    total_hours = int(task.get("total_hours") or 0)
    return max(1, total_hours // 2)


def build_pseudo_assignments(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
) -> list[PseudoAssignment]:
    """Build a deterministic pseudo schedule to create conflict/state features."""
    classrooms_by_id = {int(room["id"]): room for room in classrooms}
    teacher_slot: set[tuple[int, int]] = set()
    class_slot: set[tuple[int, int]] = set()
    room_slot: set[tuple[int, int]] = set()
    assignments: list[PseudoAssignment] = []

    for task in tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        classroom_id = int(task.get("bound_classroom_id") or classrooms[0]["id"])
        if classroom_id not in classrooms_by_id:
            classroom_id = int(classrooms[0]["id"])

        assigned_count = 0
        for slot in time_slots:
            slot_id = int(slot["id"])
            teacher_key = (teacher_id, slot_id)
            room_key = (classroom_id, slot_id)
            class_keys = [(class_group_id, slot_id) for class_group_id in class_group_ids]
            if teacher_key in teacher_slot or room_key in room_slot:
                continue
            if any(class_key in class_slot for class_key in class_keys):
                continue

            teacher_slot.add(teacher_key)
            room_slot.add(room_key)
            for class_key in class_keys:
                class_slot.add(class_key)
            assignments.append(
                PseudoAssignment(
                    task_id=task_id,
                    teacher_id=teacher_id,
                    class_group_ids=class_group_ids,
                    classroom_id=classroom_id,
                    time_slot_id=slot_id,
                    week_number=int(slot["week_number"]),
                    day_of_week=int(slot["day_of_week"]),
                    period_index=int(slot["period_index"]),
                )
            )
            assigned_count += 1
            if assigned_count >= periods_needed(task):
                break

    return assignments


def build_occupied_indexes(assignments: list[PseudoAssignment]) -> dict[str, Any]:
    indexes: dict[str, Any] = {
        "teacher_slot": defaultdict(set),
        "class_slot": defaultdict(set),
        "room_slot": defaultdict(set),
        "teacher_day_load": defaultdict(int),
        "class_day_load": defaultdict(int),
        "room_day_load": defaultdict(int),
        "scheme_day_load": defaultdict(int),
        "task_day_load": defaultdict(int),
        "teacher_week_load": defaultdict(int),
        "class_week_load": defaultdict(int),
        "room_week_load": defaultdict(int),
    }
    for assignment in assignments:
        slot_id = assignment.time_slot_id
        week_day = (assignment.week_number, assignment.day_of_week)
        teacher_day = (assignment.teacher_id, *week_day)
        room_day = (assignment.classroom_id, *week_day)
        teacher_week = (assignment.teacher_id, assignment.week_number)
        room_week = (assignment.classroom_id, assignment.week_number)
        task_day = (assignment.task_id, *week_day)

        indexes["teacher_slot"][(assignment.teacher_id, slot_id)].add(assignment.task_id)
        indexes["room_slot"][(assignment.classroom_id, slot_id)].add(assignment.task_id)
        indexes["teacher_day_load"][teacher_day] += 1
        indexes["room_day_load"][room_day] += 1
        indexes["scheme_day_load"][week_day] += 1
        indexes["task_day_load"][task_day] += 1
        indexes["teacher_week_load"][teacher_week] += 1
        indexes["room_week_load"][room_week] += 1

        for class_group_id in assignment.class_group_ids:
            class_day = (class_group_id, *week_day)
            class_week = (class_group_id, assignment.week_number)
            indexes["class_slot"][(class_group_id, slot_id)].add(assignment.task_id)
            indexes["class_day_load"][class_day] += 1
            indexes["class_week_load"][class_week] += 1
    return indexes


def is_room_type_match(required_room_type: str, room_type: str | None) -> bool:
    if not required_room_type:
        return True
    if not room_type:
        return False
    return required_room_type == room_type or required_room_type in room_type or room_type in required_room_type


def score_sample(
    *,
    has_hard_conflict: bool,
    is_type_match: bool,
    capacity_ratio: float,
    is_early_period: int,
    is_late_period: int,
    teacher_day_load: int,
    class_day_load: int,
    teacher_week_load: int,
    teacher_max_weekly_hours: int | None,
) -> float:
    if has_hard_conflict:
        return 0.0

    score = 0.60
    if is_type_match:
        score += 0.10
    if 0.50 <= capacity_ratio <= 0.90:
        score += 0.10
    if not is_early_period and not is_late_period:
        score += 0.05
    if teacher_day_load <= 3:
        score += 0.05
    if class_day_load <= 3:
        score += 0.05
    if teacher_max_weekly_hours is None or teacher_week_load * 2 <= teacher_max_weekly_hours:
        score += 0.05
    return round(min(max(score, 0.0), 1.0), 4)


def reject_reason(
    *,
    teacher_conflict: bool,
    class_conflict: bool,
    room_conflict: bool,
    capacity_enough: bool,
    type_match: bool,
) -> str:
    reasons: list[str] = []
    if teacher_conflict:
        reasons.append("teacher_conflict")
    if class_conflict:
        reasons.append("class_conflict")
    if room_conflict:
        reasons.append("room_conflict")
    if not capacity_enough:
        reasons.append("capacity_not_enough")
    if not type_match:
        reasons.append("room_type_mismatch")
    return ";".join(reasons)
