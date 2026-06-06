"""Rank day/period slot candidates for one teaching task.

Model boundary:
    teaching_task + (day, period) → score

Inference: used in candidate_pool.py to pre-filter high-quality slots.
Training data: built from historical timetables (positive = actual usage).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from python.scheduling_v2.models import SchedTask

_log = logging.getLogger("ga")

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "v2" / "slot_ranker.txt"
SCHEMA_PATH = MODEL_PATH.with_name("slot_ranker_feature_schema.json")
STATS_PATH = MODEL_PATH.with_name("slot_ranker_stats.json")

SLOT_RANK_FEATURES = [
    # Task features
    "course_code_code",
    "class_group_name_code",
    "teacher_department_code",
    "class_group_major_code",
    "course_type_code",
    "total_hours",
    "total_lessons",
    "student_count",
    # Slot features
    "day_of_week",
    "period_index",
    "is_early",
    "is_late",
    "is_morning",
    "is_afternoon",
    # Historical slot preference features
    "course_slot_frequency",
    "teacher_slot_frequency",
    "class_major_slot_frequency",
    "global_slot_frequency",
]


def rank_slots(
    task: SchedTask,
    day_periods: list[tuple[int, int]],
    *,
    top_n: int | None = None,
) -> list[tuple[int, int, float]]:
    """Return (day, period, score) sorted by model prediction."""
    feasible = _feasible_slots(task, day_periods)
    if not feasible:
        return []

    model, features = _lazy_load()
    if model is None:
        ranked = _rank_by_rules(feasible, top_n=top_n)
    else:
        ranked = _rank_by_model(model, features, task, feasible)

    return ranked[:top_n] if top_n is not None else ranked


def slot_ranker_enabled() -> bool:
    model, _features = _lazy_load()
    return model is not None


def _feasible_slots(
    task: SchedTask,
    day_periods: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Filter slots by teacher hard-unavailable constraints."""
    from python.scheduling.teacher_profiles import hard_unavailable_slots

    hard_unavailable = hard_unavailable_slots(task.teacher_profile) if task.teacher_profile else set()
    return [
        (day, period)
        for day, period in day_periods
        if (day, period) not in hard_unavailable
    ]


def _rank_by_model(
    model,
    features: list[str],
    task: SchedTask,
    slots: list[tuple[int, int]],
) -> list[tuple[int, int, float]]:
    try:
        import pandas as pd

        stats = _lazy_load_stats()
        rows = [_feature_row(task, day, period, stats=stats) for day, period in slots]
        frame = pd.DataFrame([{f: row.get(f, 0.0) for f in features} for row in rows])
        predictions = model.predict(frame)
    except Exception as exc:
        _log.warning("Slot ranker prediction failed, fallback to rules: %s", exc)
        return _rank_by_rules(slots)

    scored = [
        (day, period, float(pred))
        for (day, period), pred in zip(slots, predictions)
    ]
    scored.sort(key=lambda item: -item[2])
    return scored


def _rank_by_rules(
    slots: list[tuple[int, int]],
    *,
    top_n: int | None = None,
) -> list[tuple[int, int, float]]:
    """Fallback: prefer early slots with slight randomization."""
    scored = [(day, period, 1.0 - (period - 1) * 0.1) for day, period in slots]
    scored.sort(key=lambda item: -item[2])
    result = scored[:top_n] if top_n is not None else scored
    return result


def _feature_row(
    task: SchedTask,
    day: int,
    period: int,
    *,
    stats: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Build feature vector for (task, day, period)."""
    # Task features
    course_code = str(task.raw.get("course_code") or "").strip()
    class_group_names = str(task.raw.get("class_group_names") or "").strip()
    first_class_group = class_group_names.split(",")[0].strip() if class_group_names else ""
    teacher_dept = str(task.raw.get("teacher_department") or "").strip()
    majors = str(task.raw.get("class_group_majors") or "")
    class_major = majors.split(",")[0].strip() if majors else ""

    history = _slot_history_features(task, day, period, stats or {})
    return {
        "course_code_code": float(_stable_code(course_code)),
        "class_group_name_code": float(_stable_code(first_class_group)),
        "teacher_department_code": float(_stable_code(teacher_dept)),
        "class_group_major_code": float(_stable_code(class_major)),
        "course_type_code": float(_stable_code(task.raw.get("course_type"))),
        "total_hours": float(task.total_hours or 0),
        "total_lessons": float(task.total_lessons or 0),
        "student_count": float(task.total_student_count or 0),
        "day_of_week": float(day),
        "period_index": float(period),
        "is_early": 1.0 if period == 1 else 0.0,
        "is_late": 1.0 if period >= 4 else 0.0,
        "is_morning": 1.0 if period in (1, 2) else 0.0,
        "is_afternoon": 1.0 if period >= 3 else 0.0,
        **history,
    }


def _lazy_load():
    if _lazy_load.cached_model is not None:
        if _lazy_load.cached_model is False:
            return None, _lazy_load.cached_features
        return _lazy_load.cached_model, _lazy_load.cached_features
    if not MODEL_PATH.exists():
        _log.info("Slot ranker not found at %s, rule slot ranking enabled", MODEL_PATH)
        _lazy_load.cached_model = False
        _lazy_load.cached_features = SLOT_RANK_FEATURES
        return None, SLOT_RANK_FEATURES
    try:
        import lightgbm as lgb

        model = lgb.Booster(model_file=str(MODEL_PATH))
        features = SLOT_RANK_FEATURES
        auc = 0.0
        if SCHEMA_PATH.exists():
            schema = json.loads(SCHEMA_PATH.read_text())
            features = schema.get("features", SLOT_RANK_FEATURES)
            auc = float(schema.get("auc") or 0.0)
        _log.info("Slot ranker loaded: %s features=%s auc=%.3f", MODEL_PATH, len(features), auc)
        _lazy_load.cached_model = model
        _lazy_load.cached_features = features
        return model, features
    except Exception as exc:
        _log.warning("Failed to load slot ranker, rule slot ranking enabled: %s", exc)
        _lazy_load.cached_model = False
        _lazy_load.cached_features = SLOT_RANK_FEATURES
        return None, SLOT_RANK_FEATURES


_lazy_load.cached_model = None
_lazy_load.cached_features = SLOT_RANK_FEATURES


def _lazy_load_stats() -> dict[str, Any]:
    if _lazy_load_stats.cached_stats is not None:
        return _lazy_load_stats.cached_stats
    if not STATS_PATH.exists():
        _lazy_load_stats.cached_stats = {}
        return {}
    try:
        _lazy_load_stats.cached_stats = json.loads(STATS_PATH.read_text())
    except Exception as exc:
        _log.warning("Failed to load slot ranker stats, historical features disabled: %s", exc)
        _lazy_load_stats.cached_stats = {}
    return _lazy_load_stats.cached_stats


_lazy_load_stats.cached_stats = None


def _slot_history_features(
    task: SchedTask,
    day: int,
    period: int,
    stats: dict[str, Any],
) -> dict[str, float]:
    course_code = str(task.raw.get("course_code") or "").strip()
    teacher_dept = str(task.raw.get("teacher_department") or "").strip()
    majors = str(task.raw.get("class_group_majors") or "")
    class_major = majors.split(",")[0].strip() if majors else ""
    slot = f"{day}:{period}"
    return {
        "course_slot_frequency": _frequency(stats, "course_slot_frequency", course_code, slot),
        "teacher_slot_frequency": _frequency(stats, "teacher_slot_frequency", teacher_dept, slot),
        "class_major_slot_frequency": _frequency(stats, "class_major_slot_frequency", class_major, slot),
        "global_slot_frequency": _frequency(stats, "global_slot_frequency", "", slot),
    }


def _frequency(stats: dict[str, Any], section: str, key: str, slot: str) -> float:
    data = stats.get(section) or {}
    if section == "global_slot_frequency":
        return float(data.get(slot) or 0.0)
    return float((data.get(_norm(key)) or {}).get(slot) or 0.0)


def _norm(value: Any) -> str:
    raw = str(value or "").strip().lower()
    replacements = {
        "计算机房": "机房",
        "电脑室": "机房",
        "多媒体教室": "普通教室",
        "阶梯教室": "普通教室",
        "教室": "普通教室",
    }
    return replacements.get(raw, raw)


def _stable_code(value: Any, modulo: int = 997) -> int:
    text = str(value or "").strip().lower()
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1
