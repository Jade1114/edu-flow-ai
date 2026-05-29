"""Generate LightGBM training samples for Edu-Flow-AI scheduling.

Output:
    ../data/base/samples.csv

A single row represents:
    TeachingTask + candidate TimeSlot + candidate Classroom + current schedule state -> score
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.db.config import connect, load_db_config
from ml.db.repositories import fetch_classrooms, fetch_tasks, fetch_teacher_profiles, fetch_time_slots
from ml.scheduling.domain.features import (
    build_occupied_indexes,
    build_pseudo_assignments,
    effective_required_room_type,
    is_room_type_match,
    parse_id_tuple,
    periods_needed,
    reject_reason,
    score_sample,
)
from ml.scheduling.domain.teacher_profile import parse_optional_int, parse_unavailable_time


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_PATH = DATA_DIR / "base" / "samples.csv"

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
    "score",
    "reject_reason",
]


def generate_rows(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    max_rows: int | None,
    score_weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    pseudo_assignments = build_pseudo_assignments(tasks, classrooms, time_slots)
    indexes = build_occupied_indexes(pseudo_assignments)
    rows: list[dict[str, Any]] = []
    sample_id = 1

    for task in tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        required_room_type = effective_required_room_type(task)
        total_student_count = int(task.get("total_student_count") or 0)
        teacher_max_weekly_hours = task.get("teacher_max_weekly_hours")
        required_fragments = periods_needed(task)
        profile = teacher_profiles.get(teacher_id, {})
        profile_preference = profile.get("profile_preference") if isinstance(profile.get("profile_preference"), dict) else {}
        teacher_unavailable_slots = set(profile.get("unavailable_slots") or [])
        teacher_preferred_weekdays = set(profile_preference.get("preferredWeekdays") or [])
        teacher_avoid_slots = parse_unavailable_time(",".join(str(item) for item in profile_preference.get("avoidSlots") or []))
        preferred_max_weekly_hours = parse_optional_int(profile_preference.get("preferredMaxWeeklyHours")) or parse_optional_int(profile.get("max_weekly_hours")) or 0
        avoid_first_period = int(bool(profile_preference.get("avoidFirstPeriod")))
        avoid_last_period = int(bool(profile_preference.get("avoidLastPeriod")))
        prefer_compact_schedule = int(bool(profile_preference.get("preferCompactSchedule")))

        for slot in time_slots:
            slot_id = int(slot["id"])
            week_number = int(slot["week_number"])
            day_of_week = int(slot["day_of_week"])
            period_index = int(slot["period_index"])
            is_morning = int(period_index in (1, 2))
            is_afternoon = int(period_index in (3, 4))
            is_evening = int(period_index >= 5)
            is_weekend = int(day_of_week >= 6)
            is_early_period = int(period_index == 1)
            is_late_period = int(period_index >= 5)
            teacher_matrix_value = -1 if (day_of_week, period_index) in teacher_unavailable_slots else 0
            teacher_preferred_weekday_match = int(day_of_week in teacher_preferred_weekdays) if teacher_preferred_weekdays else 0
            teacher_avoid_slot_match = int((day_of_week, period_index) in teacher_avoid_slots)

            teacher_slot_tasks = indexes["teacher_slot"][(teacher_id, slot_id)] - {task_id}
            class_slot_tasks: set[int] = set()
            for class_group_id in class_group_ids:
                class_slot_tasks.update(indexes["class_slot"][(class_group_id, slot_id)] - {task_id})

            teacher_occupied = bool(teacher_slot_tasks)
            class_occupied = bool(class_slot_tasks)
            teacher_day_load = indexes["teacher_day_load"][(teacher_id, week_number, day_of_week)]
            teacher_week_load = indexes["teacher_week_load"][(teacher_id, week_number)]
            class_day_load = max(
                [indexes["class_day_load"][(class_group_id, week_number, day_of_week)] for class_group_id in class_group_ids]
                or [0]
            )
            class_week_load = max(
                [indexes["class_week_load"][(class_group_id, week_number)] for class_group_id in class_group_ids]
                or [0]
            )
            scheme_day_load = indexes["scheme_day_load"][(week_number, day_of_week)]
            task_day_load = indexes["task_day_load"][(task_id, week_number, day_of_week)]

            for room in classrooms:
                room_id = int(room["id"])
                room_capacity = int(room.get("capacity") or 0)
                room_type = room.get("classroom_type") or ""
                room_slot_tasks = indexes["room_slot"][(room_id, slot_id)] - {task_id}
                room_occupied = bool(room_slot_tasks)
                capacity_margin = room_capacity - total_student_count
                capacity_ratio = round(total_student_count / room_capacity, 4) if room_capacity > 0 else 1.0
                capacity_enough = room_capacity >= total_student_count if room_capacity > 0 else False
                type_match = is_room_type_match(required_room_type, room_type)
                teacher_conflict = teacher_occupied
                class_conflict = class_occupied
                room_conflict = room_occupied
                room_day_load = indexes["room_day_load"][(room_id, week_number, day_of_week)]
                room_week_load = indexes["room_week_load"][(room_id, week_number)]
                has_hard_conflict = teacher_conflict or class_conflict or room_conflict or not capacity_enough or not type_match
                row_score = score_sample(
                    has_hard_conflict=has_hard_conflict,
                    is_type_match=type_match,
                    capacity_ratio=capacity_ratio,
                    is_early_period=is_early_period,
                    is_late_period=is_late_period,
                    teacher_day_load=teacher_day_load,
                    class_day_load=class_day_load,
                    teacher_week_load=teacher_week_load,
                    teacher_max_weekly_hours=int(teacher_max_weekly_hours) if teacher_max_weekly_hours is not None else None,
                    weights=score_weights,
                )

                rows.append(
                    {
                        "sample_id": sample_id,
                        "teaching_task_id": task_id,
                        "candidate_classroom_id": room_id,
                        "candidate_time_slot_id": slot_id,
                        "course_type": task.get("course_type") or "",
                        "total_hours": int(task.get("total_hours") or 0),
                        "required_room_type": required_room_type,
                        "class_group_count": int(task.get("class_group_count") or 0),
                        "total_student_count": total_student_count,
                        "teacher_department": task.get("teacher_department") or "",
                        "teacher_title": task.get("teacher_title") or "",
                        "teacher_max_weekly_hours": teacher_max_weekly_hours or 0,
                        "room_capacity": room_capacity,
                        "room_type": room_type,
                        "room_building": room.get("building") or "",
                        "capacity_margin": capacity_margin,
                        "capacity_ratio": capacity_ratio,
                        "week_number": week_number,
                        "day_of_week": day_of_week,
                        "period_index": period_index,
                        "is_morning": is_morning,
                        "is_afternoon": is_afternoon,
                        "is_evening": is_evening,
                        "is_weekend": is_weekend,
                        "is_early_period": is_early_period,
                        "is_late_period": is_late_period,
                        "required_fragments": required_fragments,
                        "teacher_matrix_value": teacher_matrix_value,
                        "teacher_preferred_max_weekly_hours": preferred_max_weekly_hours,
                        "teacher_avoid_first_period": avoid_first_period,
                        "teacher_avoid_last_period": avoid_last_period,
                        "teacher_prefer_compact_schedule": prefer_compact_schedule,
                        "teacher_preferred_weekday_match": teacher_preferred_weekday_match,
                        "teacher_avoid_slot_match": teacher_avoid_slot_match,
                        "teacher_occupied_at_slot": int(teacher_occupied),
                        "class_occupied_at_slot": int(class_occupied),
                        "room_occupied_at_slot": int(room_occupied),
                        "teacher_day_load": teacher_day_load,
                        "class_day_load": class_day_load,
                        "teacher_week_load": teacher_week_load,
                        "class_week_load": class_week_load,
                        "scheme_day_load": scheme_day_load,
                        "room_day_load": room_day_load,
                        "room_week_load": room_week_load,
                        "task_day_load": task_day_load,
                        "is_capacity_enough": int(capacity_enough),
                        "is_room_type_match": int(type_match),
                        "has_teacher_conflict": int(teacher_conflict),
                        "has_class_conflict": int(class_conflict),
                        "has_room_conflict": int(room_conflict),
                        "has_hard_conflict": int(has_hard_conflict),
                        "score": row_score,
                        "reject_reason": reject_reason(
                            teacher_conflict=teacher_conflict,
                            class_conflict=class_conflict,
                            room_conflict=room_conflict,
                            capacity_enough=capacity_enough,
                            type_match=type_match,
                        ),
                    }
                )
                sample_id += 1
                if max_rows is not None and len(rows) >= max_rows:
                    return rows
    return rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LightGBM training samples for Edu-Flow-AI scheduling.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="CSV output path.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional maximum number of rows to generate.")
    parser.add_argument("--weights", type=str, default=None, help="JSON string of custom score_sample weights.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)

    if not tasks:
        raise RuntimeError("No active teaching tasks found. Seed or create teaching tasks before generating samples.")
    if not classrooms:
        raise RuntimeError("No active classrooms found. Seed or create classrooms before generating samples.")
    if not time_slots:
        raise RuntimeError("No time slots found. Seed or create time slots before generating samples.")

    score_weights = json.loads(args.weights) if args.weights else None
    rows = generate_rows(tasks, classrooms, time_slots, teacher_profiles, args.max_rows, score_weights)
    write_csv(rows, args.output)
    print(f"Generated {len(rows)} samples -> {args.output}")


if __name__ == "__main__":
    main()
