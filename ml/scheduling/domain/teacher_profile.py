"""Teacher-profile parsing helpers shared by DB repositories and feature builders."""

from __future__ import annotations

import json
from typing import Any


def parse_unavailable_time(text: str) -> set[tuple[int, int]]:
    """Parse '周一全天、周三上午' → {(1,1),(1,2)...(3,1),(3,2)}."""
    slots: set[tuple[int, int]] = set()
    if not text or not text.strip():
        return slots
    day_map: dict[str, int] = {
        "周一": 1,
        "周二": 2,
        "周三": 3,
        "周四": 4,
        "周五": 5,
        "周六": 6,
        "周日": 7,
    }
    time_map: dict[str, tuple[int, ...]] = {
        "全天": (1, 2, 3, 4, 5),
        "上午": (1, 2),
        "下午": (3, 4, 5),
    }
    for part in text.replace("、", ",").split(","):
        part = part.strip()
        if not part:
            continue
        for day_name, day_index in day_map.items():
            if day_name in part:
                remainder = part.replace(day_name, "").strip()
                periods = time_map.get(remainder, (1, 2, 3, 4, 5))
                for period in periods:
                    slots.add((day_index, period))
                break
    return slots


def parse_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_profile_preference(raw_json: str) -> dict[str, Any]:
    if not raw_json or not raw_json.strip():
        return {}
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_availability_matrix_unavailable(raw_json: str) -> set[tuple[int, int]]:
    """Parse 5x7 matrix[period-1][weekday-1]; -1 means fixed weekly unavailable."""
    slots: set[tuple[int, int]] = set()
    if not raw_json or not raw_json.strip():
        return slots
    try:
        matrix = json.loads(raw_json)
    except json.JSONDecodeError:
        return slots
    if not isinstance(matrix, list):
        return slots
    for period_index, row in enumerate(matrix[:5], start=1):
        if not isinstance(row, list):
            continue
        for weekday_index, value in enumerate(row[:7], start=1):
            if value == -1:
                slots.add((weekday_index, period_index))
    return slots


def parse_workload_max_hours(text: str) -> int | None:
    """Parse '希望每周不超过 8 课时' → 8."""
    import re

    match = re.search(r"(\d+)\s*课时", text)
    if match:
        return int(match.group(1))
    match = re.search(r"不超过\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None
