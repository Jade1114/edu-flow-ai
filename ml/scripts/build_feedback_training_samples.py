"""Build LightGBM CSV samples from backend feedback export JSON.

Label/weight strategy:
- confirmed or selected scheme items -> positive samples
- conflict item rows -> negative samples
- adjustment before state -> negative samples
- adjustment after state -> positive samples
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

FIELDNAMES = [
    "sample_id",
    "teaching_task_id",
    "candidate_classroom_id",
    "candidate_time_slot_id",
    "course_type",
    "total_hours",
    "required_room_type",
    "class_group_count",
    "total_student_count",
    "teacher_department",
    "teacher_title",
    "teacher_max_weekly_hours",
    "room_capacity",
    "room_type",
    "room_building",
    "capacity_margin",
    "capacity_ratio",
    "week_number",
    "day_of_week",
    "period_index",
    "is_morning",
    "is_afternoon",
    "is_evening",
    "is_weekend",
    "is_early_period",
    "is_late_period",
    "required_fragments",
    "teacher_matrix_value",
    "teacher_preferred_max_weekly_hours",
    "teacher_avoid_first_period",
    "teacher_avoid_last_period",
    "teacher_prefer_compact_schedule",
    "teacher_preferred_weekday_match",
    "teacher_avoid_slot_match",
    "teacher_occupied_at_slot",
    "class_occupied_at_slot",
    "room_occupied_at_slot",
    "teacher_day_load",
    "class_day_load",
    "teacher_week_load",
    "class_week_load",
    "scheme_day_load",
    "room_day_load",
    "room_week_load",
    "task_day_load",
    "is_capacity_enough",
    "is_room_type_match",
    "has_teacher_conflict",
    "has_class_conflict",
    "has_room_conflict",
    "has_hard_conflict",
    "sample_weight",
    "score",
    "reject_reason",
]

POSITIVE_FEEDBACK = {"CONFIRMED", "SELECTED"}


def normalize_key(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    camel = "".join(part.capitalize() if index else part for index, part in enumerate(key.split("_")))
    return row.get(camel)


def as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"true", "1", "yes"}


def build_item_index(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {as_int(normalize_key(item, "id")): item for item in items}


def build_scheme_feedback(feedback_rows: list[dict[str, Any]]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for feedback in feedback_rows:
        scheme_id = as_int(normalize_key(feedback, "scheme_id"))
        feedback_type = str(normalize_key(feedback, "feedback_type") or "").upper()
        result.setdefault(scheme_id, set()).add(feedback_type)
    return result


def conflict_item_ids(conflicts: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for conflict in conflicts:
        biz_type = str(normalize_key(conflict, "biz_type") or "")
        if biz_type in {"ALLOCATION_ITEM", "SCHEDULE_SEGMENT"} and not truthy(normalize_key(conflict, "resolved")):
            ids.add(as_int(normalize_key(conflict, "biz_id")))
    return ids


def base_sample(item: dict[str, Any], sample_id: str, label: float, weight: float, reason: str) -> dict[str, Any]:
    room_capacity = as_int(normalize_key(item, "room_capacity"))
    total_students = as_int(normalize_key(item, "total_student_count"))
    capacity_margin = room_capacity - total_students if room_capacity else 0
    capacity_ratio = round(total_students / room_capacity, 4) if room_capacity else 1.0
    period_index = as_int(normalize_key(item, "period_index"))
    day_of_week = as_int(normalize_key(item, "day_of_week"))
    has_conflict = not truthy(normalize_key(item, "valid")) or bool(normalize_key(item, "conflict_message")) or label <= 0

    return {
        "sample_id": sample_id,
        "teaching_task_id": as_int(normalize_key(item, "teaching_task_id")),
        "candidate_classroom_id": as_int(normalize_key(item, "classroom_id")),
        "candidate_time_slot_id": as_int(normalize_key(item, "time_slot_id")),
        "course_type": normalize_key(item, "course_type") or "UNKNOWN",
        "total_hours": as_int(normalize_key(item, "total_hours")),
        "required_room_type": normalize_key(item, "required_room_type") or "",
        "class_group_count": as_int(normalize_key(item, "class_group_count")),
        "total_student_count": total_students,
        "teacher_department": normalize_key(item, "teacher_department") or "UNKNOWN",
        "teacher_title": normalize_key(item, "teacher_title") or "UNKNOWN",
        "teacher_max_weekly_hours": as_int(normalize_key(item, "teacher_max_weekly_hours")),
        "room_capacity": room_capacity,
        "room_type": normalize_key(item, "room_type") or "UNKNOWN",
        "room_building": normalize_key(item, "room_building") or "UNKNOWN",
        "capacity_margin": capacity_margin,
        "capacity_ratio": capacity_ratio,
        "week_number": as_int(normalize_key(item, "week_number")),
        "day_of_week": day_of_week,
        "period_index": period_index,
        "is_morning": 1 if period_index in (1, 2) else 0,
        "is_afternoon": 1 if period_index in (3, 4) else 0,
        "is_evening": 1 if period_index >= 5 else 0,
        "is_weekend": 1 if day_of_week >= 6 else 0,
        "is_early_period": 1 if period_index == 1 else 0,
        "is_late_period": 1 if period_index >= 5 else 0,
        "required_fragments": max(1, as_int(normalize_key(item, "total_hours")) // 2),
        "teacher_matrix_value": as_int(normalize_key(item, "teacher_matrix_value")),
        "teacher_preferred_max_weekly_hours": as_int(normalize_key(item, "teacher_preferred_max_weekly_hours")),
        "teacher_avoid_first_period": as_int(normalize_key(item, "teacher_avoid_first_period")),
        "teacher_avoid_last_period": as_int(normalize_key(item, "teacher_avoid_last_period")),
        "teacher_prefer_compact_schedule": as_int(normalize_key(item, "teacher_prefer_compact_schedule")),
        "teacher_preferred_weekday_match": as_int(normalize_key(item, "teacher_preferred_weekday_match")),
        "teacher_avoid_slot_match": as_int(normalize_key(item, "teacher_avoid_slot_match")),
        "teacher_occupied_at_slot": as_int(normalize_key(item, "teacher_occupied_at_slot")),
        "class_occupied_at_slot": as_int(normalize_key(item, "class_occupied_at_slot")),
        "room_occupied_at_slot": as_int(normalize_key(item, "room_occupied_at_slot")),
        "teacher_day_load": as_int(normalize_key(item, "teacher_day_load")),
        "class_day_load": as_int(normalize_key(item, "class_day_load")),
        "teacher_week_load": as_int(normalize_key(item, "teacher_week_load")),
        "class_week_load": as_int(normalize_key(item, "class_week_load")),
        "scheme_day_load": as_int(normalize_key(item, "scheme_day_load")),
        "room_day_load": as_int(normalize_key(item, "room_day_load")),
        "room_week_load": as_int(normalize_key(item, "room_week_load")),
        "task_day_load": as_int(normalize_key(item, "task_day_load")),
        "is_capacity_enough": 1 if room_capacity >= total_students else 0,
        "is_room_type_match": as_int(normalize_key(item, "is_room_type_match"), 1),
        "has_teacher_conflict": as_int(normalize_key(item, "has_teacher_conflict")),
        "has_class_conflict": as_int(normalize_key(item, "has_class_conflict")),
        "has_room_conflict": as_int(normalize_key(item, "has_room_conflict")),
        "has_hard_conflict": 1 if has_conflict else as_int(normalize_key(item, "has_hard_conflict")),
        "sample_weight": weight,
        "score": label,
        "reject_reason": reason,
    }


def adjusted_sample(item: dict[str, Any], adjustment: dict[str, Any], sample_id: str, after: bool) -> dict[str, Any]:
    sample = dict(item)
    sample["classroom_id"] = normalize_key(adjustment, "to_classroom_id" if after else "from_classroom_id") or normalize_key(item, "classroom_id")
    sample["time_slot_id"] = normalize_key(adjustment, "to_time_slot_id" if after else "from_time_slot_id") or normalize_key(item, "time_slot_id")
    label = 1.0 if after else 0.0
    weight = 1.4 if after else 1.2
    reason = "adjustment_after_positive" if after else "adjustment_before_negative"
    return base_sample(sample, sample_id, label, weight, reason)


def build_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items") or []
    feedback = payload.get("feedback") or []
    adjustments = payload.get("adjustments") or []
    conflicts = payload.get("conflicts") or []
    item_by_id = build_item_index(items)
    scheme_feedback = build_scheme_feedback(feedback)
    conflicted_items = conflict_item_ids(conflicts)
    samples: list[dict[str, Any]] = []

    for item in items:
        item_id = as_int(normalize_key(item, "id"))
        scheme_id = as_int(normalize_key(item, "scheme_id"))
        feedback_types = scheme_feedback.get(scheme_id, set())
        if feedback_types & POSITIVE_FEEDBACK:
            samples.append(base_sample(item, f"confirmed_item_{item_id}", 1.0, 1.0, "confirmed_item_positive"))
        if item_id in conflicted_items or not truthy(normalize_key(item, "valid")):
            samples.append(base_sample(item, f"conflict_item_{item_id}", 0.0, 1.3, "conflict_item_negative"))

    for adjustment in adjustments:
        item_id = as_int(normalize_key(adjustment, "item_id"))
        item = item_by_id.get(item_id)
        if not item:
            continue
        adjustment_id = as_int(normalize_key(adjustment, "id"))
        samples.append(adjusted_sample(item, adjustment, f"adjustment_{adjustment_id}_before", after=False))
        samples.append(adjusted_sample(item, adjustment, f"adjustment_{adjustment_id}_after", after=True))

    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LightGBM samples from feedback export JSON.")
    parser.add_argument("--input", type=Path, required=True, help="Backend feedback export JSON path.")
    parser.add_argument("--output", type=Path, required=True, help="Output LightGBM CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    samples = build_samples(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(samples)
    print(f"Built {len(samples)} feedback training samples -> {args.output}")


if __name__ == "__main__":
    main()
