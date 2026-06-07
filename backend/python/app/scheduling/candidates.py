"""Generate V3 placement-model resource candidates for allocation tasks.

This is intentionally only the first V3 step:
teaching_task -> TopK (day_of_week, period_index, classroom) candidates -> JSONL.
It does not expand weeks, build timetable patterns, or resolve global conflicts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd

from app.db.session import connect, load_db_config
from app.db.repositories import fetch_allocation_task, fetch_all, fetch_generation_config
from app.ml.placement_direct import DirectPlacementModel, DIRECT_MODEL_PATH, parse_resource_key

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "generated" / "v3"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "placement_direct_model.txt"
SCHEMA_PATH = MODEL_DIR / "placement_direct_schema.json"
DEFAULT_TOP_K = 10
DEFAULT_RAW_TOP_K = 200
DEFAULT_ROOM_POOL_LIMIT = 80
DEFAULT_MAX_PER_ROOM = 2
DEFAULT_MAX_PER_SLOT = 3
DEFAULT_PREDICT_BATCH_SIZE = 100_000
ALLOWED_COURSE_TYPES = frozenset({"理论课", "上机课"})
ALLOWED_CLASSROOM_TYPES = frozenset({"普通教室", "机房"})


def generate_placement_candidates_jsonl(
    allocation_task_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    raw_top_k: int = DEFAULT_RAW_TOP_K,
    room_pool_limit: int = DEFAULT_ROOM_POOL_LIMIT,
    diversity_rerank: bool = True,
    max_per_room: int = DEFAULT_MAX_PER_ROOM,
    max_per_slot: int = DEFAULT_MAX_PER_SLOT,
    predict_batch_size: int = DEFAULT_PREDICT_BATCH_SIZE,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write one JSONL row per teaching task with TopK placement resources."""

    if allocation_task_id <= 0:
        raise ValueError("allocation_task_id must be positive")
    top_k = max(1, min(int(top_k), 50))
    raw_top_k = max(top_k, min(int(raw_top_k), 5000))
    room_pool_limit = max(top_k, min(int(room_pool_limit), 500))
    max_per_room = max(1, int(max_per_room))
    max_per_slot = max(1, int(max_per_slot))
    predict_batch_size = max(1_000, int(predict_batch_size))

    db = load_db_config()
    with connect(db) as conn:
        allocation_task = fetch_allocation_task(conn, allocation_task_id)
        if not allocation_task:
            raise ValueError(f"allocation task {allocation_task_id} not found")
        raw_config = fetch_generation_config(conn, allocation_task_id)
        tasks = _fetch_allocation_teaching_tasks(conn, allocation_task_id)
        classrooms = _fetch_active_classrooms(conn)

    if not tasks:
        raise ValueError(f"allocation task {allocation_task_id} has no teaching tasks")
    if not classrooms:
        raise ValueError("no active classrooms found")

    allowed_weeks = _allowed_weeks(raw_config)
    allowed_day_periods = _allowed_day_periods(raw_config)
    generated_at = _now_iso()
    model, features = _load_model()
    try:
        direct_model = DirectPlacementModel.load()
    except FileNotFoundError:
        direct_model = None
    out_dir = Path(output_dir) if output_dir else _default_output_dir(allocation_task_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "placement_candidates.jsonl"

    rows = _build_candidate_rows_batched(
        allocation_task_id=allocation_task_id,
        tasks=tasks,
        classrooms=classrooms,
        allowed_day_periods=allowed_day_periods,
        allowed_weeks=allowed_weeks,
        top_k=top_k,
        raw_top_k=raw_top_k,
        room_pool_limit=room_pool_limit,
        diversity_rerank=diversity_rerank,
        max_per_room=max_per_room,
        max_per_slot=max_per_slot,
        model=model,
        features=features,
        direct_model=direct_model,
        generated_at=generated_at,
        predict_batch_size=predict_batch_size,
    )
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    summary = {
        "allocation_task_id": allocation_task_id,
        "allocation_task_name": allocation_task.get("name"),
        "output_path": str(output_path),
        "task_count": len(rows),
        "top_k": top_k,
        "raw_top_k": raw_top_k,
        "room_pool_limit": room_pool_limit,
        "diversity_rerank": diversity_rerank,
        "max_per_room": max_per_room,
        "max_per_slot": max_per_slot,
        "predict_batch_size": predict_batch_size,
        "model_enabled": True,
        "model_mode": "direct" if direct_model else "ranker",
        "direct_model_path": str(DIRECT_MODEL_PATH) if direct_model else None,
        "model_path": str(MODEL_PATH),
        "allowed_weeks": allowed_weeks,
        "allowed_day_periods": [{"day_of_week": d, "period_index": p} for d, p in allowed_day_periods],
        "empty_candidate_count": sum(1 for row in rows if not row.get("resources")),
        "generated_at": generated_at,
    }
    (out_dir / "placement_candidates_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def _build_task_candidate_row(
    *,
    allocation_task_id: int,
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    allowed_day_periods: list[tuple[int, int]],
    allowed_weeks: list[int],
    top_k: int,
    raw_top_k: int,
    room_pool_limit: int,
    diversity_rerank: bool,
    max_per_room: int,
    max_per_slot: int,
    model: lgb.Booster,
    features: list[str],
    generated_at: str,
) -> dict[str, Any]:
    if not _is_supported_course(task):
        candidate_count = 0
        scored = []
    else:
        candidate_inputs = _enumerate_resource_candidates(
            task,
            classrooms,
            allowed_day_periods,
            room_pool_limit=room_pool_limit,
        )
        scored = _score_candidates(task, candidate_inputs, model, features) if candidate_inputs else []
        candidate_count = len(candidate_inputs)
    return _build_task_candidate_row_from_scored(
        allocation_task_id=allocation_task_id,
        task=task,
        allowed_weeks=allowed_weeks,
        top_k=top_k,
        raw_top_k=raw_top_k,
        room_pool_limit=room_pool_limit,
        diversity_rerank=diversity_rerank,
        max_per_room=max_per_room,
        max_per_slot=max_per_slot,
        candidate_count=candidate_count,
        scored=scored,
        generated_at=generated_at,
    )


def _build_candidate_rows_batched(
    *,
    allocation_task_id: int,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    allowed_day_periods: list[tuple[int, int]],
    allowed_weeks: list[int],
    top_k: int,
    raw_top_k: int,
    room_pool_limit: int,
    diversity_rerank: bool,
    max_per_room: int,
    max_per_slot: int,
    model: lgb.Booster,
    features: list[str],
    direct_model: DirectPlacementModel | None,
    generated_at: str,
    predict_batch_size: int,
) -> list[dict[str, Any]]:
    if direct_model is not None:
        return _build_candidate_rows_direct(
            allocation_task_id=allocation_task_id,
            tasks=tasks,
            classrooms=classrooms,
            allowed_day_periods=allowed_day_periods,
            allowed_weeks=allowed_weeks,
            top_k=top_k,
            raw_top_k=raw_top_k,
            room_pool_limit=room_pool_limit,
            diversity_rerank=diversity_rerank,
            max_per_room=max_per_room,
            max_per_slot=max_per_slot,
            ranker_model=model,
            ranker_features=features,
            direct_model=direct_model,
            generated_at=generated_at,
        )

    candidate_counts: list[int] = []
    feature_rows: list[dict[str, float]] = []
    feature_refs: list[tuple[int, dict[str, Any]]] = []
    scored_by_task: list[list[tuple[dict[str, Any], float]]] = [[] for _ in tasks]

    def flush_predictions() -> None:
        if not feature_rows:
            return
        frame = pd.DataFrame(feature_rows, columns=features)
        scores = model.predict(frame)
        for (task_index, candidate), score in zip(feature_refs, scores):
            scored_by_task[task_index].append((candidate, float(score)))
        feature_rows.clear()
        feature_refs.clear()

    for task_index, task in enumerate(tasks):
        if not _is_supported_course(task):
            candidate_counts.append(0)
            continue
        candidates = _enumerate_resource_candidates(
            task,
            classrooms,
            allowed_day_periods,
            room_pool_limit=room_pool_limit,
        )
        candidate_counts.append(len(candidates))
        for candidate in candidates:
            feature_rows.append(_features(task, candidate))
            feature_refs.append((task_index, candidate))
            if len(feature_rows) >= predict_batch_size:
                flush_predictions()

    flush_predictions()

    rows: list[dict[str, Any]] = []
    for task_index, task in enumerate(tasks):
        scored = sorted(scored_by_task[task_index], key=lambda item: item[1], reverse=True)
        row = _build_task_candidate_row_from_scored(
            allocation_task_id=allocation_task_id,
            task=task,
            allowed_weeks=allowed_weeks,
            top_k=top_k,
            raw_top_k=raw_top_k,
            room_pool_limit=room_pool_limit,
            diversity_rerank=diversity_rerank,
            max_per_room=max_per_room,
            max_per_slot=max_per_slot,
            candidate_count=candidate_counts[task_index],
            scored=scored,
            generated_at=generated_at,
        )
        rows.append(row)
    return rows


def _build_candidate_rows_direct(
    *,
    allocation_task_id: int,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    allowed_day_periods: list[tuple[int, int]],
    allowed_weeks: list[int],
    top_k: int,
    raw_top_k: int,
    room_pool_limit: int,
    diversity_rerank: bool,
    max_per_room: int,
    max_per_slot: int,
    ranker_model: lgb.Booster,
    ranker_features: list[str],
    direct_model: DirectPlacementModel,
    generated_at: str,
) -> list[dict[str, Any]]:
    classroom_by_name = {str(room.get("name") or "").strip(): room for room in classrooms}
    allowed_pairs = set(allowed_day_periods)
    rows: list[dict[str, Any]] = []
    fallback_count = 0
    for task in tasks:
        direct_scored = _direct_scored_candidates(
            task,
            direct_model=direct_model,
            classroom_by_name=classroom_by_name,
            allowed_day_periods=allowed_pairs,
            top_k=max(raw_top_k, top_k * 4),
        )
        selected = _select_diverse_candidates(
            direct_scored,
            top_k=top_k,
            enabled=diversity_rerank,
            max_per_room=max_per_room,
            max_per_slot=max_per_slot,
        )
        if len(selected) < top_k:
            fallback_count += 1
            fallback_row = _build_task_candidate_row(
                allocation_task_id=allocation_task_id,
                task=task,
                classrooms=classrooms,
                allowed_day_periods=allowed_day_periods,
                allowed_weeks=allowed_weeks,
                top_k=top_k,
                raw_top_k=raw_top_k,
                room_pool_limit=room_pool_limit,
                diversity_rerank=diversity_rerank,
                max_per_room=max_per_room,
                max_per_slot=max_per_slot,
                model=ranker_model,
                features=ranker_features,
                generated_at=generated_at,
            )
            fallback_row["meta"]["model_mode"] = "direct_with_ranker_fallback"
            fallback_row["meta"]["direct_model_path"] = str(DIRECT_MODEL_PATH)
            fallback_row["meta"]["direct_candidate_count"] = len(direct_scored)
            fallback_row["meta"]["fallback_used"] = True
            rows.append(fallback_row)
            continue
        row = _build_task_candidate_row_from_scored(
            allocation_task_id=allocation_task_id,
            task=task,
            allowed_weeks=allowed_weeks,
            top_k=top_k,
            raw_top_k=raw_top_k,
            room_pool_limit=room_pool_limit,
            diversity_rerank=diversity_rerank,
            max_per_room=max_per_room,
            max_per_slot=max_per_slot,
            candidate_count=len(direct_scored),
            scored=selected,
            generated_at=generated_at,
        )
        row["meta"]["model_mode"] = "direct"
        row["meta"]["direct_model_path"] = str(DIRECT_MODEL_PATH)
        row["meta"]["direct_candidate_count"] = len(direct_scored)
        row["meta"]["fallback_used"] = False
        rows.append(row)
    for row in rows:
        row["meta"]["fallback_count"] = fallback_count
    return rows


def _direct_scored_candidates(
    task: dict[str, Any],
    *,
    direct_model: DirectPlacementModel,
    classroom_by_name: dict[str, dict[str, Any]],
    allowed_day_periods: set[tuple[int, int]],
    top_k: int,
) -> list[tuple[dict[str, Any], float]]:
    if not _is_supported_course(task):
        return []
    scored = []
    task_like = _direct_task_like(task)
    for resource_key, score in direct_model.predict_topk(task_like, top_k=top_k):
        parsed = parse_resource_key(resource_key)
        if parsed is None:
            continue
        classroom_name, day, period = parsed
        if (day, period) not in allowed_day_periods:
            continue
        classroom = classroom_by_name.get(classroom_name)
        if not classroom or not _is_feasible_room(task, classroom):
            continue
        scored.append((_candidate_from_direct(classroom, day, period), score))
    return scored


def _direct_task_like(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_name": task.get("course_name") or "",
        "course_code": task.get("course_code") or "",
        "teacher_no": task.get("teacher_no") or "",
        "teacher_name": task.get("teacher_name") or "",
        "class_name": task.get("class_group_names") or "",
        "class_major": task.get("class_group_majors") or "",
        "class_department": task.get("class_group_departments") or "",
        "class_grade": task.get("class_group_grades") or "",
        "student_count": task.get("total_student_count") or 0,
        "total_hours": task.get("total_hours") or 0,
        "course_type": task.get("course_type") or "",
        "required_room_type": task.get("required_room_type") or "",
    }


def _candidate_from_direct(classroom: dict[str, Any], day: int, period: int) -> dict[str, Any]:
    return {
        "day_of_week": int(day),
        "period_index": int(period),
        "classroom_id": int(classroom["id"]),
        "room_name": classroom.get("name") or "",
        "room_type": classroom.get("classroom_type") or "",
        "room_capacity": int(classroom.get("capacity") or 0),
        "building": classroom.get("building") or "",
    }


def _build_task_candidate_row_from_scored(
    *,
    allocation_task_id: int,
    task: dict[str, Any],
    allowed_weeks: list[int],
    top_k: int,
    raw_top_k: int,
    room_pool_limit: int,
    diversity_rerank: bool,
    max_per_room: int,
    max_per_slot: int,
    candidate_count: int,
    scored: list[tuple[dict[str, Any], float]],
    generated_at: str,
) -> dict[str, Any]:
    if not _is_supported_course(task):
        resources = []
        error = "UNSUPPORTED_COURSE_TYPE"
    else:
        selected = _select_diverse_candidates(
            scored[:raw_top_k],
            top_k=top_k,
            enabled=diversity_rerank,
            max_per_room=max_per_room,
            max_per_slot=max_per_slot,
        )
        resources = [
            _to_resource(rank, candidate, score)
            for rank, (candidate, score) in enumerate(selected, start=1)
        ]
        error = None if resources else "NO_CANDIDATES"
    row = {
        "allocation_task_id": allocation_task_id,
        "teaching_task_id": int(task["teaching_task_id"]),
        "task": {
            "total_hours": int(task.get("total_hours") or 0),
            "total_sessions": max(0, int(task.get("total_hours") or 0) // 2),
            "course_type": task.get("course_type") or "",
            "required_room_type": task.get("required_room_type") or "",
            "teacher_id": task.get("teacher_id"),
            "class_group_ids": _parse_id_list(task.get("class_group_ids")),
        },
        "input": {
            "course_name": task.get("course_name") or "",
            "course_code": task.get("course_code") or "",
            "teacher_no": task.get("teacher_no") or "",
            "teacher_name": task.get("teacher_name") or "",
            "class_name": task.get("class_group_names") or "",
        },
        "resources": resources,
        "meta": {
            "top_k": top_k,
            "raw_top_k": raw_top_k,
            "room_pool_limit": room_pool_limit,
            "diversity_rerank": diversity_rerank,
            "max_per_room": max_per_room,
            "max_per_slot": max_per_slot,
            "candidate_count": candidate_count,
            "allowed_weeks": allowed_weeks,
            "model_enabled": True,
            "model_version": "v3-placement-model",
            "model_path": str(MODEL_PATH),
            "generated_at": generated_at,
        },
    }
    if error:
        row["error"] = error
    return row


def _load_model() -> tuple[lgb.Booster, list[str]]:
    if not MODEL_PATH.exists() or not SCHEMA_PATH.exists():
        raise FileNotFoundError("V3 placement model is missing. Train it before generating candidates.")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return lgb.Booster(model_file=str(MODEL_PATH)), schema["features"]


def _score_candidates(
    task: dict[str, Any],
    candidates: list[dict[str, Any]],
    model: lgb.Booster,
    features: list[str],
) -> list[tuple[dict[str, Any], float]]:
    rows = [_features(task, candidate) for candidate in candidates]
    frame = pd.DataFrame(rows, columns=features)
    scores = model.predict(frame)
    return sorted(
        ((candidate, float(score)) for candidate, score in zip(candidates, scores)),
        key=lambda item: item[1],
        reverse=True,
    )


def _select_diverse_candidates(
    scored: list[tuple[dict[str, Any], float]],
    *,
    top_k: int,
    enabled: bool,
    max_per_room: int,
    max_per_slot: int,
) -> list[tuple[dict[str, Any], float]]:
    if not enabled or len(scored) <= top_k:
        return scored[:top_k]

    selected: list[tuple[dict[str, Any], float]] = []
    selected_ids: set[tuple[int, int, int]] = set()
    room_counts: dict[int, int] = {}
    slot_counts: dict[tuple[int, int], int] = {}

    for candidate, score in scored:
        room_id = int(candidate.get("classroom_id") or 0)
        slot_key = (int(candidate.get("day_of_week") or 0), int(candidate.get("period_index") or 0))
        identity = (room_id, *slot_key)
        if identity in selected_ids:
            continue
        if room_counts.get(room_id, 0) >= max_per_room:
            continue
        if slot_counts.get(slot_key, 0) >= max_per_slot:
            continue
        selected.append((candidate, score))
        selected_ids.add(identity)
        room_counts[room_id] = room_counts.get(room_id, 0) + 1
        slot_counts[slot_key] = slot_counts.get(slot_key, 0) + 1
        if len(selected) >= top_k:
            return selected

    for candidate, score in scored:
        room_id = int(candidate.get("classroom_id") or 0)
        slot_key = (int(candidate.get("day_of_week") or 0), int(candidate.get("period_index") or 0))
        identity = (room_id, *slot_key)
        if identity in selected_ids:
            continue
        selected.append((candidate, score))
        selected_ids.add(identity)
        if len(selected) >= top_k:
            break
    return selected


def _features(task: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    encoded = {
        "course_name_code": _stable_code(task.get("course_name")),
        "course_code_code": _stable_code(task.get("course_code")),
        "teacher_no_code": _stable_code(task.get("teacher_no")),
        "teacher_name_code": _stable_code(task.get("teacher_name")),
        "class_name_code": _stable_code(task.get("class_group_names")),
        "class_major_code": _stable_code(task.get("class_group_majors")),
        "class_department_code": _stable_code(task.get("class_group_departments")),
        "course_type_code": _stable_code(task.get("course_type")),
        "required_room_type_code": _stable_code(task.get("required_room_type")),
        "classroom_name_code": _stable_code(candidate.get("room_name")),
        "classroom_type_code": _stable_code(candidate.get("room_type")),
    }
    student_count = float(task.get("total_student_count") or 0)
    room_capacity = float(candidate.get("room_capacity") or 0)
    numeric = {
        "class_grade": float(_first_int(task.get("class_group_grades"))),
        "class_no": float(_extract_class_no(str(task.get("class_group_names") or ""))),
        "student_count": student_count,
        "total_hours": float(task.get("total_hours") or 0),
        "day_of_week": float(candidate.get("day_of_week") or 0),
        "period_index": float(candidate.get("period_index") or 0),
        "classroom_capacity": room_capacity,
        "capacity_margin": room_capacity - student_count,
        "capacity_ratio": student_count / max(1.0, room_capacity),
        "is_room_type_match": 1.0 if _norm(task.get("required_room_type")) == _norm(candidate.get("room_type")) else 0.0,
    }
    return {**encoded, **numeric}


def _enumerate_resource_candidates(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    allowed_day_periods: list[tuple[int, int]],
    *,
    room_pool_limit: int,
) -> list[dict[str, Any]]:
    feasible_rooms = [
        classroom for classroom in classrooms
        if _is_feasible_room(task, classroom)
    ]
    feasible_rooms = _rank_room_pool(task, feasible_rooms)[:room_pool_limit]
    candidates: list[dict[str, Any]] = []
    for classroom in feasible_rooms:
        for day, period in allowed_day_periods:
            candidates.append({
                "day_of_week": day,
                "period_index": period,
                "classroom_id": int(classroom["id"]),
                "room_name": classroom.get("name") or "",
                "room_type": classroom.get("classroom_type") or "",
                "room_capacity": int(classroom.get("capacity") or 0),
                "building": classroom.get("building") or "",
            })
    return candidates


def _stable_code(value: Any, modulo: int = 10007) -> float:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return 0.0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return float(total + 1)


def _rank_room_pool(task: dict[str, Any], classrooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first V3 step responsive before global optimization exists.

    The placement model still scores the final room+slot pairs. This prefilter only
    prevents very large classroom catalogs from creating millions of rows per task.
    """

    student_count = int(task.get("total_student_count") or 0)

    def key(classroom: dict[str, Any]) -> tuple[int, int, int]:
        capacity = int(classroom.get("capacity") or 0)
        capacity_margin = capacity - student_count if student_count > 0 else 0
        usable_margin = capacity_margin if capacity_margin >= 0 else 999_999
        room_name = str(classroom.get("name") or "")
        return (
            0 if capacity_margin >= 0 else 1,
            usable_margin,
            _room_name_order(room_name),
        )

    return sorted(classrooms, key=key)


def _room_name_order(value: str) -> int:
    digits = "".join(char for char in value if char.isdigit())
    return int(digits[:8]) if digits else 999_999_999


def _to_resource(rank: int, candidate: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "rank": rank,
        "slot": {
            "day_of_week": int(candidate["day_of_week"]),
            "period_index": int(candidate["period_index"]),
        },
        "classroom": {
            "id": int(candidate["classroom_id"]),
            "name": candidate.get("room_name") or "",
            "type": candidate.get("room_type") or "",
            "capacity": int(candidate.get("room_capacity") or 0),
            "building": candidate.get("building") or "",
        },
        "score": round(float(score), 6),
        "source": "placement_model",
    }


def _fetch_allocation_teaching_tasks(conn, allocation_task_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT
            tt.id AS teaching_task_id,
            tt.primary_teacher_id AS teacher_id,
            t.employee_no AS teacher_no,
            t.name AS teacher_name,
            t.department AS teacher_department,
            tt.total_hours,
            COALESCE(tt.required_room_type, c.required_room_type) AS required_room_type,
            c.name AS course_name,
            c.code AS course_code,
            c.course_type,
            COUNT(cg.id) AS class_group_count,
            COALESCE(SUM(cg.student_count), 0) AS total_student_count,
            GROUP_CONCAT(cg.id ORDER BY cg.id) AS class_group_ids,
            GROUP_CONCAT(cg.name ORDER BY cg.id) AS class_group_names,
            GROUP_CONCAT(cg.major ORDER BY cg.id) AS class_group_majors,
            GROUP_CONCAT(cg.department ORDER BY cg.id) AS class_group_departments,
            GROUP_CONCAT(cg.grade ORDER BY cg.id) AS class_group_grades
        FROM allocation_task_teaching_task att
        JOIN teaching_task tt ON tt.id = att.teaching_task_id
        JOIN course c ON c.id = tt.course_id
        JOIN teacher t ON t.id = tt.primary_teacher_id
        LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
        LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
        WHERE att.allocation_task_id = %s
          AND tt.status = 'ACTIVE'
          AND c.course_type IN ('理论课', '上机课')
        GROUP BY
            tt.id,
            tt.primary_teacher_id,
            t.employee_no,
            t.name,
            t.department,
            tt.total_hours,
            tt.required_room_type,
            c.name,
            c.code,
            c.course_type,
            c.required_room_type
        ORDER BY tt.id
        """,
        (allocation_task_id,),
    )


def _fetch_active_classrooms(conn) -> list[dict[str, Any]]:
    classrooms = fetch_all(
        conn,
        """
        SELECT id, name, building, capacity, classroom_type
        FROM classroom
        WHERE status = 'ACTIVE'
          AND classroom_type IN ('普通教室', '机房')
          AND LOWER(name) NOT LIKE 'xn%%'
          AND name NOT LIKE '虚拟%%'
          AND name NOT LIKE '%%操场%%'
          AND name NOT LIKE '%%体育%%'
        ORDER BY id
        """,
    )
    return [classroom for classroom in classrooms if _is_supported_classroom(classroom)]


def _allowed_day_periods(raw_config: dict[str, Any] | None) -> list[tuple[int, int]]:
    allowed_days = _parse_int_set(raw_config.get("allowed_weekdays") if raw_config else None)
    allowed_periods = _parse_int_set(raw_config.get("allowed_periods") if raw_config else None)
    days = sorted(allowed_days or set(range(1, 8)))
    periods = sorted(allowed_periods or set(range(1, 6)))
    return [(day, period) for day in days for period in periods]


def _allowed_weeks(raw_config: dict[str, Any] | None) -> list[int]:
    allowed = _parse_int_set(raw_config.get("allowed_weeks") if raw_config else None)
    return sorted(allowed or set(range(1, 19)))


def _parse_int_set(value: Any) -> set[int] | None:
    if value is None:
        return None
    raw = str(value).strip().strip("[]").replace(" ", "")
    if not raw:
        return None
    result: set[int] = set()
    for part in raw.split(","):
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result or None


def _is_feasible_room(task: dict[str, Any], classroom: dict[str, Any]) -> bool:
    if not _is_supported_classroom(classroom):
        return False
    capacity = int(classroom.get("capacity") or 0)
    student_count = int(task.get("total_student_count") or 0)
    if student_count > 0 and capacity > 0 and capacity < student_count:
        return False
    required = _norm(task.get("required_room_type"))
    room_type = _norm(classroom.get("classroom_type"))
    if required and room_type and required != room_type:
        return False
    return True


def _is_supported_course(task: dict[str, Any]) -> bool:
    return str(task.get("course_type") or "").strip() in ALLOWED_COURSE_TYPES


def _is_supported_classroom(classroom: dict[str, Any]) -> bool:
    room_type = str(classroom.get("classroom_type") or "").strip()
    name = str(classroom.get("name") or "").strip().lower()
    if room_type not in ALLOWED_CLASSROOM_TYPES:
        return False
    if name.startswith("xn") or name.startswith("虚拟"):
        return False
    return "操场" not in name and "体育" not in name


def _parse_id_list(value: Any) -> list[int]:
    if value is None:
        return []
    result = []
    for part in str(value).split(","):
        try:
            parsed = int(part.strip())
        except ValueError:
            continue
        if parsed > 0:
            result.append(parsed)
    return result


def _first_int(value: Any) -> int:
    for part in str(value or "").split(","):
        try:
            return int(float(part.strip()))
        except ValueError:
            continue
    return 0


def _extract_class_no(value: str) -> int:
    if "班" not in value:
        return 0
    before = value.split("班")[0]
    digits = ""
    for char in reversed(before):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return int(digits) if digits else 0


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


def _default_output_dir(allocation_task_id: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return OUTPUT_ROOT / f"task_{allocation_task_id}_{stamp}"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V3 placement candidates JSONL.")
    parser.add_argument("allocation_task_id", type=int)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--raw-top-k", type=int, default=DEFAULT_RAW_TOP_K)
    parser.add_argument("--room-pool-limit", type=int, default=DEFAULT_ROOM_POOL_LIMIT)
    parser.add_argument("--no-diversity-rerank", action="store_true")
    parser.add_argument("--max-per-room", type=int, default=DEFAULT_MAX_PER_ROOM)
    parser.add_argument("--max-per-slot", type=int, default=DEFAULT_MAX_PER_SLOT)
    parser.add_argument("--predict-batch-size", type=int, default=DEFAULT_PREDICT_BATCH_SIZE)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    summary = generate_placement_candidates_jsonl(
        args.allocation_task_id,
        top_k=args.top_k,
        raw_top_k=args.raw_top_k,
        room_pool_limit=args.room_pool_limit,
        diversity_rerank=not args.no_diversity_rerank,
        max_per_room=args.max_per_room,
        max_per_slot=args.max_per_slot,
        predict_batch_size=args.predict_batch_size,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
