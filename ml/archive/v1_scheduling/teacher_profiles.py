"""Runtime teacher-profile helpers for scheduling.

The parser accepts both the future JSONL snapshot format and the current DB
profile shape returned by repositories.fetch_teacher_profiles().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.scheduling.types import slot_to_day_period


DEFAULT_SOFT_AVOID_PENALTY = 60.0
AVOID_PERIOD_PENALTY = 40.0
PREFERRED_WEEKDAY_MISS_PENALTY = 10.0
PREFERRED_PERIOD_MISS_PENALTY = 8.0
COMPACT_DAY_PENALTY = 20.0
MAX_DAILY_LESSON_PENALTY = 100.0
MAX_WEEKLY_LESSON_PENALTY = 200.0


def load_teacher_profiles_jsonl(path: str | Path | None) -> dict[int, dict[str, Any]]:
    if not path:
        return {}
    profile_path = Path(path)
    if not profile_path.exists():
        return {}

    profiles: dict[int, dict[str, Any]] = {}
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        teacher_id = _to_int(row.get("teacher_id"))
        if not teacher_id:
            continue
        profiles[teacher_id] = normalize_profile(row)
    return profiles


def normalize_profiles(raw_profiles: dict | None) -> dict[int, dict[str, Any]]:
    if not raw_profiles:
        return {}
    normalized: dict[int, dict[str, Any]] = {}
    for key, value in raw_profiles.items():
        teacher_id = _to_int(key)
        if not teacher_id:
            continue
        normalized[teacher_id] = normalize_profile(value)
    return normalized


def normalize_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty_profile()

    profile = raw.get("profile") if isinstance(raw.get("profile"), dict) else raw
    normalized = _empty_profile()
    normalized["raw_text"] = str(raw.get("raw_text") or raw.get("rawText") or "")
    normalized["parser_version"] = str(raw.get("parser_version") or raw.get("parserVersion") or "")

    hard_slots = set()
    hard_slots.update(_parse_slot_rules(profile.get("hard_unavailable")))
    hard_slots.update(_parse_slot_rules(profile.get("hardUnavailable")))
    hard_slots.update(_coerce_slot_set(profile.get("hard_unavailable")))
    hard_slots.update(_coerce_slot_set(profile.get("hardUnavailable")))
    hard_slots.update(_coerce_slot_set(raw.get("unavailable_slots")))
    hard_slots.update(_parse_availability_matrix(raw.get("availability_matrix_json") or raw.get("availabilityMatrixJson")))
    normalized["hard_unavailable"] = hard_slots

    soft_avoid = []
    for item in _as_list(profile.get("soft_avoid") or profile.get("softAvoid") or profile.get("avoidSlots")):
        if not isinstance(item, dict):
            continue
        weekday = _valid_weekday(item.get("weekday"))
        periods = _valid_periods(item.get("periods") or item.get("period"))
        if weekday is None or not periods:
            continue
        soft_avoid.append({
            "weekday": weekday,
            "periods": periods,
            "penalty": _clamp_float(item.get("penalty"), 0.0, 100.0, DEFAULT_SOFT_AVOID_PENALTY),
            "reason": str(item.get("reason") or "教师软避让"),
        })
    normalized["soft_avoid"] = soft_avoid

    preference = raw.get("profile_preference") if isinstance(raw.get("profile_preference"), dict) else {}
    normalized["preferred_weekdays"] = _valid_weekdays(
        profile.get("preferred_weekdays")
        or profile.get("preferredWeekdays")
        or preference.get("preferredWeekdays")
    )
    normalized["preferred_periods"] = _valid_periods(profile.get("preferred_periods") or profile.get("preferredPeriods"))
    avoid_periods = _valid_periods(profile.get("avoid_periods") or profile.get("avoidPeriods"))
    if profile.get("avoidFirstPeriod") and 1 not in avoid_periods:
        avoid_periods.append(1)
    if profile.get("avoidLastPeriod") and 5 not in avoid_periods:
        avoid_periods.append(5)
    normalized["avoid_periods"] = avoid_periods
    normalized["prefer_compact_schedule"] = bool(
        profile.get("prefer_compact_schedule")
        or profile.get("preferCompactSchedule")
        or preference.get("preferCompactSchedule")
    )
    normalized["max_daily_lessons"] = _positive_int(profile.get("max_daily_lessons") or profile.get("maxDailyLessons"))
    normalized["max_weekly_lessons"] = _positive_int(
        profile.get("max_weekly_lessons")
        or profile.get("maxWeeklyLessons")
        or profile.get("teacher_preferred_max_weekly_hours")
        or profile.get("preferredMaxWeeklyHours")
        or preference.get("preferredMaxWeeklyHours")
        or raw.get("max_weekly_hours")
    )
    normalized["notes"] = str(profile.get("notes") or "")
    return normalized


def hard_unavailable_slots(profile: dict[str, Any] | None) -> set[tuple[int, int]]:
    if not profile:
        return set()
    return set(profile.get("hard_unavailable") or set())


def profile_penalty(
    profile: dict[str, Any] | None,
    slot_id: int,
    *,
    day_load: int = 0,
    week_load: int = 0,
    day_count_for_task: int = 0,
) -> tuple[float, list[dict[str, Any]]]:
    if not profile:
        return 0.0, []

    day, period = slot_to_day_period(slot_id)
    penalty = 0.0
    breakdown: list[dict[str, Any]] = []

    for item in profile.get("soft_avoid") or []:
        if item["weekday"] == day and period in item["periods"]:
            value = float(item["penalty"])
            penalty += value
            breakdown.append({"rule": "soft_avoid", "penalty": value, "reason": item["reason"]})

    if period in set(profile.get("avoid_periods") or []):
        penalty += AVOID_PERIOD_PENALTY
        breakdown.append({"rule": "avoid_period", "penalty": AVOID_PERIOD_PENALTY, "reason": f"教师偏好避开第{period}节"})

    preferred_weekdays = set(profile.get("preferred_weekdays") or [])
    if preferred_weekdays and day not in preferred_weekdays:
        penalty += PREFERRED_WEEKDAY_MISS_PENALTY
        breakdown.append({"rule": "preferred_weekday_miss", "penalty": PREFERRED_WEEKDAY_MISS_PENALTY, "reason": "未命中教师偏好星期"})

    preferred_periods = set(profile.get("preferred_periods") or [])
    if preferred_periods and period not in preferred_periods:
        penalty += PREFERRED_PERIOD_MISS_PENALTY
        breakdown.append({"rule": "preferred_period_miss", "penalty": PREFERRED_PERIOD_MISS_PENALTY, "reason": "未命中教师偏好节次"})

    max_daily = profile.get("max_daily_lessons")
    if max_daily and day_load > int(max_daily):
        penalty += MAX_DAILY_LESSON_PENALTY
        breakdown.append({"rule": "max_daily_lessons", "penalty": MAX_DAILY_LESSON_PENALTY, "reason": "超过教师每日课次偏好"})

    max_weekly = profile.get("max_weekly_lessons")
    if max_weekly and week_load > int(max_weekly):
        penalty += MAX_WEEKLY_LESSON_PENALTY
        breakdown.append({"rule": "max_weekly_lessons", "penalty": MAX_WEEKLY_LESSON_PENALTY, "reason": "超过教师每周课次偏好"})

    if profile.get("prefer_compact_schedule") and day_count_for_task > 1:
        penalty += COMPACT_DAY_PENALTY
        breakdown.append({"rule": "compact_schedule", "penalty": COMPACT_DAY_PENALTY, "reason": "教师偏好集中排课"})

    return penalty, breakdown


def profile_explanation(breakdown: list[dict[str, Any]]) -> str:
    return "；".join(str(item.get("reason") or item.get("rule")) for item in breakdown)


def _empty_profile() -> dict[str, Any]:
    return {
        "hard_unavailable": set(),
        "soft_avoid": [],
        "preferred_weekdays": [],
        "preferred_periods": [],
        "avoid_periods": [],
        "prefer_compact_schedule": False,
        "max_daily_lessons": None,
        "max_weekly_lessons": None,
        "raw_text": "",
        "parser_version": "",
        "notes": "",
    }


def _parse_slot_rules(value: Any) -> set[tuple[int, int]]:
    slots: set[tuple[int, int]] = set()
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        weekday = _valid_weekday(item.get("weekday"))
        periods = _valid_periods(item.get("periods") or item.get("period"))
        if weekday is None:
            continue
        for period in periods:
            slots.add((weekday, period))
    return slots


def _coerce_slot_set(value: Any) -> set[tuple[int, int]]:
    slots: set[tuple[int, int]] = set()
    for item in _as_list(value):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            weekday = _valid_weekday(item[0])
            period = _valid_period(item[1])
            if weekday is not None and period is not None:
                slots.add((weekday, period))
    return slots


def _parse_availability_matrix(value: Any) -> set[tuple[int, int]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return set()
    if not isinstance(value, list):
        return set()

    slots: set[tuple[int, int]] = set()
    for period_index, row in enumerate(value[:5], start=1):
        if not isinstance(row, list):
            continue
        for weekday, cell in enumerate(row[:7], start=1):
            if _to_int(cell) == -1:
                slots.add((weekday, period_index))
    return slots


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _valid_weekdays(value: Any) -> list[int]:
    result = []
    for item in _as_list(value):
        weekday = _valid_weekday(item)
        if weekday is not None and weekday not in result:
            result.append(weekday)
    return result


def _valid_periods(value: Any) -> list[int]:
    if value == "*":
        return [1, 2, 3, 4, 5]
    result = []
    for item in _as_list(value):
        if item == "*":
            return [1, 2, 3, 4, 5]
        period = _valid_period(item)
        if period is not None and period not in result:
            result.append(period)
    return result


def _valid_weekday(value: Any) -> int | None:
    parsed = _to_int(value)
    return parsed if parsed is not None and 1 <= parsed <= 7 else None


def _valid_period(value: Any) -> int | None:
    parsed = _to_int(value)
    return parsed if parsed is not None and 1 <= parsed <= 5 else None


def _positive_int(value: Any) -> int | None:
    parsed = _to_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp_float(value: Any, min_value: float, max_value: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))
