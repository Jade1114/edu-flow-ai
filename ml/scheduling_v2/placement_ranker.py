"""Placement ranker for teaching_task + room + slot candidates."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

_log = logging.getLogger("ga")

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "v2" / "placement_ranker.txt"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "models" / "v2" / "placement_ranker_feature_schema.json"
STATS_PATH = Path(__file__).resolve().parents[1] / "models" / "v2" / "placement_ranker_stats.json"

PLACEMENT_RANK_FEATURES = [
    "course_code_code",
    "course_name_code",
    "course_type_code",
    "teacher_name_code",
    "teacher_department_code",
    "class_group_name_code",
    "class_group_major_code",
    "class_grade",
    "class_no",
    "student_count",
    "total_hours",
    "total_lessons",
    "room_name_code",
    "room_type_code",
    "room_capacity",
    "capacity_margin",
    "capacity_ratio",
    "required_type_match",
    "building_code",
    "day_of_week",
    "period_index",
    "is_early",
    "is_late",
    "is_morning",
    "is_afternoon",
    "course_slot_frequency",
    "teacher_slot_frequency",
    "class_major_slot_frequency",
    "room_slot_frequency",
    "course_room_frequency",
    "teacher_room_frequency",
    "class_major_room_frequency",
    "course_room_slot_frequency",
    "teacher_room_slot_frequency",
    "major_room_slot_frequency",
    "global_room_slot_frequency",
]


def placement_ranker_enabled() -> bool:
    model, _features, _stats = _lazy_load()
    return model is not None


def score_placements(task: Any, candidates: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float]]:
    """Rank placement candidates. Candidate dict needs room/day/period-like fields."""
    model, features, stats = _lazy_load()
    rows = [_features_for_candidate(task, candidate, stats) for candidate in candidates]
    if model is None:
        return sorted(
            ((candidate, _fallback_score(row)) for candidate, row in zip(candidates, rows)),
            key=lambda item: item[1],
            reverse=True,
        )
    import pandas as pd

    frame = pd.DataFrame(rows, columns=features)
    scores = model.predict(frame)
    return sorted(
        ((candidate, float(score)) for candidate, score in zip(candidates, scores)),
        key=lambda item: item[1],
        reverse=True,
    )


@lru_cache(maxsize=1)
def _lazy_load():
    try:
        if not MODEL_PATH.exists() or not SCHEMA_PATH.exists():
            return None, PLACEMENT_RANK_FEATURES, _load_stats()
        import lightgbm as lgb

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        features = schema.get("features") or PLACEMENT_RANK_FEATURES
        model = lgb.Booster(model_file=str(MODEL_PATH))
        _log.info("Placement ranker loaded: %s", MODEL_PATH)
        return model, features, _load_stats()
    except Exception as exc:
        _log.warning("Placement ranker disabled: %s", exc)
        return None, PLACEMENT_RANK_FEATURES, _load_stats()


def _load_stats() -> dict[str, Any]:
    if not STATS_PATH.exists():
        return {}
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _features_for_candidate(task: Any, candidate: dict[str, Any], stats: dict[str, Any]) -> dict[str, float]:
    course_code = _get(task, "course_code")
    course_name = _get(task, "course_name")
    teacher_name = _get(task, "teacher_name") or _get(task, "teacher")
    class_group_name = _get(task, "class_group_name") or _get(task, "class_group_names") or _get(task, "class_group")
    class_major = _get(task, "class_group_major") or _get(task, "class_group_majors") or _get(task, "major")
    teacher_department = _get(task, "teacher_department") or teacher_name
    course_type = _get(task, "course_type")
    total_hours = _as_float(_get(task, "total_hours"))
    student_count = _as_float(_get(task, "student_count") or _get(task, "total_student_count"))
    room_name = _get(candidate, "room_name") or _get(candidate, "room")
    room_type = _norm(_get(candidate, "room_type") or _get(candidate, "classroom_type"))
    room_capacity = _as_float(_get(candidate, "room_capacity") or _get(candidate, "capacity"))
    required_room_type = _norm(_get(task, "required_room_type"))
    day = _as_int(_get(candidate, "day") or _get(candidate, "day_of_week"))
    period = _as_int(_get(candidate, "period") or _get(candidate, "period_index"))
    slot_key = f"{day}:{period}"
    room_slot_key = f"{room_name}|{slot_key}"
    return {
        "course_code_code": float(_stable_code(course_code)),
        "course_name_code": float(_stable_code(course_name)),
        "course_type_code": float(_stable_code(course_type)),
        "teacher_name_code": float(_stable_code(teacher_name)),
        "teacher_department_code": float(_stable_code(teacher_department)),
        "class_group_name_code": float(_stable_code(class_group_name)),
        "class_group_major_code": float(_stable_code(class_major)),
        "class_grade": float(_extract_grade(class_group_name)),
        "class_no": float(_extract_class_no(class_group_name)),
        "student_count": student_count,
        "total_hours": total_hours,
        "total_lessons": total_hours / 2.0,
        "room_name_code": float(_stable_code(room_name)),
        "room_type_code": float(_stable_code(room_type)),
        "room_capacity": room_capacity,
        "capacity_margin": room_capacity - student_count,
        "capacity_ratio": student_count / max(1.0, room_capacity),
        "required_type_match": 1.0 if required_room_type and required_room_type == room_type else 0.0,
        "building_code": float(_building_code(room_name)),
        "day_of_week": float(day),
        "period_index": float(period),
        "is_early": 1.0 if period == 1 else 0.0,
        "is_late": 1.0 if period >= 4 else 0.0,
        "is_morning": 1.0 if period in (1, 2) else 0.0,
        "is_afternoon": 1.0 if period >= 3 else 0.0,
        "course_slot_frequency": _frequency(stats, "course_slot_frequency", course_code, slot_key),
        "teacher_slot_frequency": _frequency(stats, "teacher_slot_frequency", teacher_name, slot_key),
        "class_major_slot_frequency": _frequency(stats, "class_major_slot_frequency", class_major, slot_key),
        "room_slot_frequency": _frequency(stats, "room_slot_frequency", room_name, slot_key),
        "course_room_frequency": _frequency(stats, "course_room_frequency", course_code, room_name),
        "teacher_room_frequency": _frequency(stats, "teacher_room_frequency", teacher_name, room_name),
        "class_major_room_frequency": _frequency(stats, "class_major_room_frequency", class_major, room_name),
        "course_room_slot_frequency": _frequency(stats, "course_room_slot_frequency", course_code, room_slot_key),
        "teacher_room_slot_frequency": _frequency(stats, "teacher_room_slot_frequency", teacher_name, room_slot_key),
        "major_room_slot_frequency": _frequency(stats, "major_room_slot_frequency", class_major, room_slot_key),
        "global_room_slot_frequency": _frequency(stats, "global_room_slot_frequency", "", room_slot_key),
    }


def _fallback_score(row: dict[str, float]) -> float:
    return (
        row.get("course_room_slot_frequency", 0.0)
        + row.get("teacher_room_slot_frequency", 0.0)
        + row.get("major_room_slot_frequency", 0.0)
        + row.get("global_room_slot_frequency", 0.0)
        + row.get("required_type_match", 0.0) * 0.05
    )


def _frequency(stats: dict[str, Any], section: str, key: str, item: str) -> float:
    data = stats.get(section) or {}
    if section == "global_room_slot_frequency":
        return float(data.get(item) or 0.0)
    return float((data.get(_norm(key)) or {}).get(item) or 0.0)


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    value = getattr(obj, key, None)
    if value is not None:
        return value
    raw = getattr(obj, "raw", None)
    if isinstance(raw, dict):
        return raw.get(key)
    return None


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _norm(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "")
    replacements = {
        "计算机房": "机房",
        "电脑室": "机房",
        "多媒体教室": "普通教室",
        "阶梯教室": "普通教室",
        "教室": "普通教室",
    }
    return replacements.get(raw, raw)


def _stable_code(value: Any, modulo: int = 997) -> int:
    text = _norm(value)
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1


def _building_code(value: Any) -> int:
    text = str(value or "").strip()
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return int(digits[:4])
    return _stable_code(text, modulo=97)


def _extract_grade(value: Any) -> int:
    text = str(value or "")
    for index in range(max(0, len(text) - 3)):
        part = text[index:index + 4]
        if part.isdigit() and 2000 <= int(part) <= 2100:
            return int(part)
    return 0


def _extract_class_no(value: Any) -> int:
    text = str(value or "")
    if "班" not in text:
        return 0
    before = text.split("班")[0]
    digits = ""
    for char in reversed(before):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return int(digits) if digits else 0
