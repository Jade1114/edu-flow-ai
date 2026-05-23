"""Filtering helpers for scheduling tasks and time slots."""

from __future__ import annotations

from typing import Any


def filter_tasks(tasks: list[dict[str, Any]], teaching_task_ids: set[int] | None) -> list[dict[str, Any]]:
    if not teaching_task_ids:
        return tasks
    ordered_tasks = [task for task in tasks if int(task["teaching_task_id"]) in teaching_task_ids]
    missing_ids = teaching_task_ids - {int(task["teaching_task_id"]) for task in ordered_tasks}
    if missing_ids:
        raise ValueError(f"Teaching tasks not found or inactive: {sorted(missing_ids)}")
    return ordered_tasks


def filter_time_slots(
    time_slots: list[dict[str, Any]],
    start_week: int | None,
    end_week: int | None,
    allowed_weeks: set[int] | None = None,
    allowed_weekdays: set[int] | None = None,
    allowed_periods: set[int] | None = None,
) -> list[dict[str, Any]]:
    return [
        slot
        for slot in time_slots
        if (start_week is None or int(slot["week_number"]) >= start_week)
        and (end_week is None or int(slot["week_number"]) <= end_week)
        and (allowed_weeks is None or int(slot["week_number"]) in allowed_weeks)
        and (allowed_weekdays is None or int(slot["day_of_week"]) in allowed_weekdays)
        and (allowed_periods is None or int(slot["period_index"]) in allowed_periods)
    ]


def parse_teaching_task_ids(raw_value: str | None) -> set[int] | None:
    if not raw_value:
        return None
    return {int(value.strip()) for value in raw_value.split(",") if value.strip()}
