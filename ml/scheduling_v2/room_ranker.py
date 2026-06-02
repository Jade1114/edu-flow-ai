"""Rank classroom candidates for one teaching task.

The model boundary here is intentionally narrow:

    teaching_task + classrooms -> ranked classrooms

Day/period/template choices stay in the candidate-pool rules, so model
inference is O(tasks * classrooms), not O(tasks * classrooms * slots).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ml.scheduling_v2.models import SchedTask

_log = logging.getLogger("ga")

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "v2" / "room_ranker.txt"
SCHEMA_PATH = MODEL_PATH.with_name("room_ranker_feature_schema.json")

ROOM_RANK_FEATURES = [
    "student_count",
    "total_hours",
    "total_lessons",
    "room_capacity",
    "capacity_margin",
    "capacity_ratio",
    "required_type_match",
    "course_type_code",
    "required_room_type_code",
    "room_type_code",
    "building_code",
    "teacher_department_code",
    "class_group_major_code",
    "course_code_code",
    "class_group_name_code",
]


def rank_rooms(
    task: SchedTask,
    classrooms: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Return feasible rooms sorted by ranker score, with rule fallback."""

    feasible = _feasible_rooms(task, classrooms)
    if not feasible:
        return []

    model, features = _lazy_load()
    if model is None:
        ranked = _rank_by_rules(task, feasible)
    else:
        ranked = _rank_by_model(model, features, task, feasible)

    if top_n is not None:
        return ranked[:top_n]
    return ranked


def room_ranker_enabled() -> bool:
    model, _features = _lazy_load()
    return model is not None


def _feasible_rooms(
    task: SchedTask,
    classrooms: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required_type = _resolve_required_type(task)
    feasible: list[dict[str, Any]] = []
    for room in classrooms:
        room_id = int(room.get("id") or 0)
        capacity = int(room.get("capacity") or 0)
        room_type = _norm(room.get("classroom_type") or "")
        if room_id <= 0:
            continue
        if capacity < task.total_student_count:
            continue
        if not room_type:
            continue
        if required_type != room_type:
            continue
        feasible.append(dict(room))
    return feasible


def _resolve_required_type(task: SchedTask) -> str:
    """Resolve the required classroom type from task data or course_type."""
    explicit = _norm(task.required_room_type or task.raw.get("bound_classroom_type") or "")
    if explicit:
        return explicit
    # Infer from course_type when no explicit room type is set
    course_type = _norm(str(task.raw.get("course_type") or ""))
    type_map = {
        "理论课": "普通教室",
        "上机课": "机房",
        "实践课": "普通教室",
        "体育课": "操场",
    }
    inferred = type_map.get(course_type, "")
    if inferred:
        return inferred
    # Last fallback: do not filter by room type (all types allowed)
    return ""


def _rank_by_model(model, features: list[str], task: SchedTask, rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        import pandas as pd

        rows = [_feature_row(task, room) for room in rooms]
        frame = pd.DataFrame([{feature: row.get(feature, 0.0) for feature in features} for row in rows])
        predictions = model.predict(frame)
    except Exception as exc:
        _log.warning("Room ranker prediction failed, fallback to rules: %s", exc)
        return _rank_by_rules(task, rooms)

    scored: list[tuple[float, dict[str, Any]]] = []
    for room, prediction in zip(rooms, predictions, strict=False):
        room_with_score = dict(room)
        room_with_score["_rank_score"] = float(prediction)
        room_with_score["_rank_source"] = "model"
        scored.append((float(prediction), room_with_score))
    return _sort_ranked(task, scored)


def _rank_by_rules(task: SchedTask, rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    bound_room_id = int(task.raw.get("bound_classroom_id") or 0)
    required_type = _norm(task.required_room_type or task.raw.get("bound_classroom_type") or "")
    for room in rooms:
        capacity = int(room.get("capacity") or 0)
        room_type = _norm(room.get("classroom_type") or "")
        waste = capacity - task.total_student_count
        type_bonus = 20.0 if required_type and required_type == room_type else 0.0
        bound_bonus = 100.0 if int(room.get("id") or 0) == bound_room_id else 0.0
        score = bound_bonus + type_bonus - waste / max(1, capacity)
        room_with_score = dict(room)
        room_with_score["_rank_score"] = score
        room_with_score["_rank_source"] = "rules"
        scored.append((score, room_with_score))
    return _sort_ranked(task, scored)


def _sort_ranked(task: SchedTask, scored: list[tuple[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    bound_room_id = int(task.raw.get("bound_classroom_id") or 0)
    scored.sort(key=lambda item: (-item[0], int(item[1].get("id") or 0)))

    bound_rooms = [room for _score, room in scored if int(room.get("id") or 0) == bound_room_id]
    other_rooms = [room for _score, room in scored if int(room.get("id") or 0) != bound_room_id]
    return bound_rooms + other_rooms


def _feature_row(task: SchedTask, room: dict[str, Any]) -> dict[str, float]:
    student_count = int(task.total_student_count or 0)
    capacity = int(room.get("capacity") or 0)
    required_type = _resolve_required_type(task)
    room_type = _norm(room.get("classroom_type") or "")

    # Teacher department: from DB query t.department
    teacher_dept = str(task.raw.get("teacher_department") or "").strip()
    # Class group major: from GROUP_CONCAT(cg.major), take first if comma-separated
    majors = str(task.raw.get("class_group_majors") or "")
    class_major = majors.split(",")[0].strip() if majors else ""
    # Course code: unique identifier for each course
    course_code = str(task.raw.get("course_code") or "").strip()
    # Class group name: unique identifier for each class group
    class_group_names = str(task.raw.get("class_group_names") or "").strip()
    first_class_group = class_group_names.split(",")[0].strip() if class_group_names else ""

    return {
        "student_count": float(student_count),
        "total_hours": float(task.total_hours or 0),
        "total_lessons": float(task.total_lessons or 0),
        "room_capacity": float(capacity),
        "capacity_margin": float(capacity - student_count),
        "capacity_ratio": float(student_count / max(1, capacity)),
        "required_type_match": 1.0 if required_type and required_type == room_type else 0.0,
        "course_type_code": float(_stable_code(task.raw.get("course_type"))),
        "required_room_type_code": float(_stable_code(required_type)),
        "room_type_code": float(_stable_code(room_type)),
        "building_code": float(_building_code(room.get("building") or room.get("name"))),
        "teacher_department_code": float(_stable_code(teacher_dept)),
        "class_group_major_code": float(_stable_code(class_major)),
        "course_code_code": float(_stable_code(course_code)),
        "class_group_name_code": float(_stable_code(first_class_group)),
    }


def _lazy_load():
    if _lazy_load.cached_model is not None:
        if _lazy_load.cached_model is False:
            return None, _lazy_load.cached_features
        return _lazy_load.cached_model, _lazy_load.cached_features
    if not MODEL_PATH.exists():
        _log.info("Room ranker not found at %s, rule room ranking enabled", MODEL_PATH)
        _lazy_load.cached_model = False
        _lazy_load.cached_features = ROOM_RANK_FEATURES
        return None, ROOM_RANK_FEATURES
    try:
        import lightgbm as lgb

        model = lgb.Booster(model_file=str(MODEL_PATH))
        features = ROOM_RANK_FEATURES
        auc = 0.0
        if SCHEMA_PATH.exists():
            schema = json.loads(SCHEMA_PATH.read_text())
            features = schema.get("features", ROOM_RANK_FEATURES)
            auc = float(schema.get("auc") or 0.0)
        _log.info("Room ranker loaded: %s features=%s auc=%.3f", MODEL_PATH, len(features), auc)
        _lazy_load.cached_model = model
        _lazy_load.cached_features = features
        return model, features
    except Exception as exc:
        _log.warning("Failed to load room ranker, rule room ranking enabled: %s", exc)
        _lazy_load.cached_model = False
        _lazy_load.cached_features = ROOM_RANK_FEATURES
        return None, ROOM_RANK_FEATURES


_lazy_load.cached_model = None
_lazy_load.cached_features = ROOM_RANK_FEATURES


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
    text = _norm(value)
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1


def _building_code(value: Any) -> int:
    text = _norm(value)
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return int(digits[:4])
    return _stable_code(text, modulo=97)
