"""Generation-config adapters for scheduling pipelines."""

from __future__ import annotations

import json
from typing import Any

from ml.scheduling.infra.constants import DEFAULT_RULE_WEIGHTS


def build_generation_config_json(raw_config: dict[str, Any]) -> str:
    """Convert a DB generation config row to the JSON format consumed by GA."""
    config = {
        "allowedWeeks": str(raw_config.get("allowed_weeks", "")),
        "allowedWeekdays": str(raw_config.get("allowed_weekdays", "")),
        "allowedPeriods": str(raw_config.get("allowed_periods", "")),
        "schemeCount": int(raw_config.get("scheme_count", 3)),
        "teacherProfilePenaltyScale": float(raw_config.get("teacher_profile_penalty_scale", 80.0)),
        "distributionPenaltyScale": float(raw_config.get("distribution_penalty_scale", 10.0)),
        "classroomStickinessWeight": float(raw_config.get("classroom_stickiness_weight", 15.0)),
        "compactBonusWeight": float(raw_config.get("compact_bonus_weight", 0.0)),
    }
    for src, dst in [
        ("weekday_load_penalty", "weekdayLoadPenalty"),
        ("room_day_load_penalty", "roomDayLoadPenalty"),
        ("room_week_load_penalty", "roomWeekLoadPenalty"),
        ("task_day_load_penalty", "taskDayLoadPenalty"),
        ("early_period_penalty", "earlyPeriodPenalty"),
        ("late_period_penalty", "latePeriodPenalty"),
        ("random_jitter", "randomJitter"),
        ("classroom_stickiness_bonus", "classroomStickinessBonus"),
        ("weekend_penalty", "weekendPenalty"),
    ]:
        value = raw_config.get(src)
        if value is not None:
            config[dst] = float(value)
    return json.dumps(config, ensure_ascii=False)


def load_generation_config(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise ValueError("generation-config must be a JSON object")
    return payload


def config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    return config.get(key) if config.get(key) is not None else default


def config_float(config: dict[str, Any], key: str, default: float) -> float:
    value = config_value(config, key, default)
    return float(value)


def rule_weights_from_config(config: dict[str, Any]) -> dict[str, float]:
    mapping = {
        "weekdayLoadPenalty": "weekday_load_penalty",
        "roomDayLoadPenalty": "room_day_load_penalty",
        "roomWeekLoadPenalty": "room_week_load_penalty",
        "taskDayLoadPenalty": "task_day_load_penalty",
        "earlyPeriodPenalty": "early_period_penalty",
        "latePeriodPenalty": "late_period_penalty",
        "compactBonusWeight": "compact_bonus_weight",
        "randomJitter": "random_jitter",
        "classroomStickinessBonus": "classroom_stickiness_bonus",
        "weekendPenalty": "weekend_penalty",
    }
    weights = dict(DEFAULT_RULE_WEIGHTS)
    for source, target in mapping.items():
        if config.get(source) is not None:
            weights[target] = float(config[source])
    return weights
