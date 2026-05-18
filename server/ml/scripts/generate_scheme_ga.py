"""Generate scheduling schemes with GA + LightGBM.

LightGBM scores local scheduling candidates. The genetic algorithm searches complete
scheme combinations globally. Java persists the CSV output and does not call
LLM/RAG services — this script may call LLM to parse teacher profile texts
into structured penalties.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ml_logger

try:
    import lightgbm as lgb
except ImportError:
    lgb = None
import numpy as np
import pandas as pd

from generate_training_samples import (
    PseudoAssignment,
    build_occupied_indexes,
    connect,
    effective_required_room_type,
    fetch_classrooms,
    fetch_tasks,
    fetch_teacher_profiles,
    fetch_time_slots,
    is_room_type_match,
    load_db_config,
    parse_id_tuple,
    periods_needed,
    reject_reason,
    score_sample,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT_DIR.parents[1]
PROJECT_LOG_DIR = PROJECT_ROOT / "logs"
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"
OUTPUT_PATH = ROOT_DIR / "data" / "generated_scheme_ga.csv"
OUTPUT_DIR = ROOT_DIR / "data" / "generated_schemes"
SUMMARY_PATH = OUTPUT_DIR / "summary.csv"
GA_SUMMARY_PATH = OUTPUT_DIR / "ga_summary.json"

OUTPUT_COLUMNS = [
    "sequence",
    "teaching_task_id",
    "teacher_id",
    "teacher_name",
    "fragment_index",
    "classroom_id",
    "time_slot_id",
    "week_number",
    "day_of_week",
    "period_index",
    "predicted_score",
    "rule_score",
    "has_hard_conflict",
    "reject_reason",
    "teacher_profile_penalty",
    "teacher_profile_penalty_explanation",
    "teacher_profile_penalty_breakdown",
]

TEACHER_PENALTIES_FILENAME = "teacher_penalties.json"
LOG_PREFIX = "[SCHEDULE-CHAIN]"
PYTHON_LOG_FILE: Optional[Path] = None
CANDIDATE_DIAGNOSTICS: dict[int, dict[str, Any]] = {}
RUN_TIMINGS: Counter[str] = Counter()

SUMMARY_COLUMNS = [
    "scheme_no",
    "output_path",
    "tasks",
    "expected_fragments",
    "generated_fragments",
    "hard_conflict_fragments",
    "avg_predicted_score",
    "avg_rule_score",
    "fitness",
    "hard_conflict_count",
    "candidate_hard_conflict_count",
    "teacher_slot_conflict_count",
    "room_slot_conflict_count",
    "class_slot_conflict_count",
    "teacher_profile_penalty_total",
    "distribution_penalty",
    "classroom_switches",
    "candidate_pool_count",
]

WEEKDAY_LOAD_PENALTY = 0.004
ROOM_DAY_LOAD_PENALTY = 0.012
ROOM_WEEK_LOAD_PENALTY = 0.003
TASK_DAY_LOAD_PENALTY = 0.018
RANDOM_JITTER = 0.002
DEFAULT_CANDIDATE_POOL_SIZE = 500
DEFAULT_CANDIDATE_TOP_N = 100
DEFAULT_POPULATION_SIZE = 160
DEFAULT_GENERATIONS = 200
DEFAULT_ELITE_SIZE = 16
DEFAULT_TOURNAMENT_SIZE = 6
DEFAULT_MUTATION_RATE = 0.12
DEFAULT_PREDICTED_SCORE_WEIGHT = 100.0
DEFAULT_RULE_SCORE_WEIGHT = 10.0
DEFAULT_HARD_CONFLICT_PENALTY = 100000.0
DEFAULT_TEACHER_PROFILE_PENALTY_SCALE = 50.0
DEFAULT_DISTRIBUTION_PENALTY_SCALE = 5.0
DEFAULT_CLASSROOM_STICKINESS_WEIGHT = 5.0
DEFAULT_COMPACT_BONUS_WEIGHT = 0.0

POLICY_PROFILES = {
    "BALANCED": {
        "weekday_load_penalty": 0.008,
        "room_day_load_penalty": 0.005,
        "room_week_load_penalty": 0.002,
        "task_day_load_penalty": 0.012,
        "early_period_penalty": 0.012,
        "late_period_penalty": 0.008,
        "compact_bonus_weight": 0.0,
        "random_jitter": 0.002,
        "classroom_stickiness_bonus": 0.006,
        "weekend_penalty": 0.01
    },
    "TEACHER_FRIENDLY": {
        "weekday_load_penalty": 0.006,
        "room_day_load_penalty": 0.004,
        "room_week_load_penalty": 0.001,
        "task_day_load_penalty": 0.025,
        "early_period_penalty": 0.04,
        "late_period_penalty": 0.03,
        "compact_bonus_weight": 0.0,
        "random_jitter": 0.001,
        "classroom_stickiness_bonus": 0.004,
        "weekend_penalty": 0.015
    },
    "CLASS_BALANCED": {
        "weekday_load_penalty": 0.012,
        "room_day_load_penalty": 0.004,
        "room_week_load_penalty": 0.001,
        "task_day_load_penalty": 0.008,
        "early_period_penalty": 0.01,
        "late_period_penalty": 0.01,
        "compact_bonus_weight": 0.0,
        "random_jitter": 0.002,
        "classroom_stickiness_bonus": 0.005,
        "weekend_penalty": 0.008
    },
    "ROOM_EFFICIENT": {
        "weekday_load_penalty": 0.002,
        "room_day_load_penalty": 0.025,
        "room_week_load_penalty": 0.01,
        "task_day_load_penalty": 0.005,
        "early_period_penalty": 0.005,
        "late_period_penalty": 0.005,
        "compact_bonus_weight": 0.0,
        "random_jitter": 0.003,
        "classroom_stickiness_bonus": 0.008,
        "weekend_penalty": 0.01
    },
    "COMPACT": {
        "weekday_load_penalty": 0.002,
        "room_day_load_penalty": 0.008,
        "room_week_load_penalty": 0.002,
        "task_day_load_penalty": 0.01,
        "early_period_penalty": 0.005,
        "late_period_penalty": 0.005,
        "compact_bonus_weight": 0.015,
        "random_jitter": 0.002,
        "classroom_stickiness_bonus": 0.003,
        "weekend_penalty": 0.005
    }
}



DEFAULT_POLICY = "BALANCED"


def configure_python_log(log_file: Optional[Path]) -> None:
    global PYTHON_LOG_FILE
    PYTHON_LOG_FILE = log_file
    if PYTHON_LOG_FILE is not None:
        PYTHON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        PYTHON_LOG_FILE.write_text("", encoding="utf-8")


def add_timing(name: str, started_at: float) -> None:
    RUN_TIMINGS[name] += round((perf_counter() - started_at) * 1000, 3)


def log_chain(message: str, payload: Any | None = None) -> None:
    if payload is None:
        line = f"{LOG_PREFIX} {message}"
    else:
        line = f"{LOG_PREFIX} {message}: {json.dumps(payload, ensure_ascii=False, default=str)}"
    print(line, flush=True)
    if PYTHON_LOG_FILE is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with PYTHON_LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {line}\n")
    # Also persist to persistent service log
    ml_logger.service.info("%s %s", LOG_PREFIX, line)


def load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}. Run train_lightgbm.py first.")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_optional_lightgbm(model_path: Path, schema_path: Path) -> tuple[Optional[Any], Optional[dict[str, Any]], str]:
    if lgb is None:
        log_chain("LightGBM 未安装，GA 将仅使用规则软评分排序候选", {"fallback": "rule_score_fallback"})
        return None, None, "rule_score_fallback"
    if model_path.exists() and schema_path.exists():
        return lgb.Booster(model_file=str(model_path)), load_schema(schema_path), "lightgbm"
    missing = []
    if not model_path.exists():
        missing.append(str(model_path))
    if not schema_path.exists():
        missing.append(str(schema_path))
    log_chain("LightGBM 模型不可用，GA 将仅使用规则软评分排序候选", {"missing": missing})
    return None, None, "rule_score_fallback"


def diagnose_candidate_space(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profile: Optional[dict[str, Any]],
    exclude_weekends: bool,
) -> dict[str, Any]:
    required_capacity = int(task.get("total_student_count") or 0)
    required_room_type = effective_required_room_type(task)
    bound_classroom_id = task.get("bound_classroom_id")
    normalized_unavailable = {
        tuple(slot) for slot in normalize_unavailable_slots((teacher_profile or {}).get("unavailable_slots"))
    }
    available_time_slots = [
        slot for slot in time_slots
        if not (exclude_weekends and int(slot["day_of_week"]) >= 6)
        and (int(slot["day_of_week"]), int(slot["period_index"])) not in normalized_unavailable
    ]
    capacity_valid_rooms = [room for room in classrooms if int(room.get("capacity") or 0) >= required_capacity]
    type_valid_rooms = [room for room in capacity_valid_rooms if is_room_type_match(required_room_type, room.get("classroom_type") or "")]
    final_rooms = type_valid_rooms
    filtered_reasons = {}
    if not available_time_slots:
        filtered_reasons["teacher_or_weekend_time_unavailable"] = len(time_slots)
    if not capacity_valid_rooms:
        filtered_reasons["capacity_not_enough"] = len(classrooms)
    elif not type_valid_rooms:
        filtered_reasons["room_type_mismatch"] = len(capacity_valid_rooms)
    return {
        "task_id": int(task["teaching_task_id"]),
        "teacher_id": int(task["teacher_id"]),
        "teacher_name": task.get("teacher_name") or "",
        "required_fragments": periods_needed(task),
        "required_capacity": required_capacity,
        "required_room_type": required_room_type,
        "bound_classroom_id": bound_classroom_id,
        "available_time_slot_count": len(available_time_slots),
        "available_classrooms": [
            {
                "id": int(room["id"]),
                "name": room.get("name") or room.get("classroom_name") or "",
                "capacity": int(room.get("capacity") or 0),
                "type": room.get("classroom_type") or "",
                "building": room.get("building") or "",
            }
            for room in sorted(final_rooms, key=lambda item: int(item.get("capacity") or 0), reverse=True)[:20]
        ],
        "max_available_capacity": max([int(room.get("capacity") or 0) for room in final_rooms] or [0]),
        "has_any_available_classroom": bool(final_rooms),
        "has_any_feasible_candidate": bool(final_rooms and available_time_slots),
        "filtered_reason": filtered_reasons or {"ok": 0},
        "suggestions": {
            "allow_split_class": required_capacity > max([int(room.get("capacity") or 0) for room in classrooms] or [0]),
            "allow_room_type_relaxation": bool(required_room_type and capacity_valid_rooms and not type_valid_rooms),
            "allow_capacity_expansion": not bool(capacity_valid_rooms),
            "allow_bound_room_change": bool(bound_classroom_id and type_valid_rooms),
        },
    }


def build_candidate_rows(
    *,
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    selected_assignments: list[PseudoAssignment],
    teacher_profile: Optional[dict[str, Any]] = None,
    exclude_weekends: bool = False,
) -> list[dict[str, Any]]:
    indexes = build_occupied_indexes(selected_assignments)
    scheme_day_load = Counter((assignment.week_number, assignment.day_of_week) for assignment in selected_assignments)
    room_day_load = Counter(
        (assignment.classroom_id, assignment.week_number, assignment.day_of_week) for assignment in selected_assignments
    )
    room_week_load = Counter((assignment.classroom_id, assignment.week_number) for assignment in selected_assignments)
    task_day_load = Counter(
        (assignment.task_id, assignment.week_number, assignment.day_of_week) for assignment in selected_assignments
    )
    task_id = int(task["teaching_task_id"])
    teacher_id = int(task["teacher_id"])
    class_group_ids = parse_id_tuple(task.get("class_group_ids"))
    required_room_type = effective_required_room_type(task)
    total_student_count = int(task.get("total_student_count") or 0)
    teacher_max_weekly_hours = task.get("teacher_max_weekly_hours")
    bound_classroom_id = task.get("bound_classroom_id")
    unavailable_slots = {
        tuple(slot) for slot in normalize_unavailable_slots((teacher_profile or {}).get("unavailable_slots"))
    }
    filter_started_at = perf_counter()
    filtered_time_slots = [
        slot for slot in time_slots
        if not (exclude_weekends and int(slot["day_of_week"]) >= 6)
        and (int(slot["day_of_week"]), int(slot["period_index"])) not in unavailable_slots
    ]
    filtered_classrooms = [
        room for room in classrooms
        if int(room.get("capacity") or 0) >= total_student_count
        and is_room_type_match(required_room_type, room.get("classroom_type") or "")
    ]
    add_timing("candidate_filter_time", filter_started_at)
    rows: list[dict[str, Any]] = []

    for slot in filtered_time_slots:
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

        teacher_occupied = bool(indexes["teacher_slot"][(teacher_id, slot_id)])
        class_occupied = any(bool(indexes["class_slot"][(class_group_id, slot_id)]) for class_group_id in class_group_ids)
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

        for room in filtered_classrooms:
            room_id = int(room["id"])
            room_capacity = int(room.get("capacity") or 0)
            room_type = room.get("classroom_type") or ""
            room_occupied = bool(indexes["room_slot"][(room_id, slot_id)])
            capacity_margin = room_capacity - total_student_count
            capacity_ratio = round(total_student_count / room_capacity, 4) if room_capacity > 0 else 1.0
            capacity_enough = room_capacity >= total_student_count if room_capacity > 0 else False
            type_match = is_room_type_match(required_room_type, room_type)
            teacher_conflict = teacher_occupied
            class_conflict = class_occupied
            room_conflict = room_occupied
            has_hard_conflict = teacher_conflict or class_conflict or room_conflict or not capacity_enough or not type_match
            rule_score = score_sample(
                has_hard_conflict=has_hard_conflict,
                is_type_match=type_match,
                capacity_ratio=capacity_ratio,
                is_early_period=is_early_period,
                is_late_period=is_late_period,
                teacher_day_load=teacher_day_load,
                class_day_load=class_day_load,
                teacher_week_load=teacher_week_load,
                teacher_max_weekly_hours=int(teacher_max_weekly_hours) if teacher_max_weekly_hours is not None else None,
            )

            rows.append(
                {
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
                    "teacher_occupied_at_slot": int(teacher_occupied),
                    "class_occupied_at_slot": int(class_occupied),
                    "room_occupied_at_slot": int(room_occupied),
                    "teacher_day_load": teacher_day_load,
                    "class_day_load": class_day_load,
                    "teacher_week_load": teacher_week_load,
                    "class_week_load": class_week_load,
                    "scheme_day_load": scheme_day_load[(week_number, day_of_week)],
                    "room_day_load": room_day_load[(room_id, week_number, day_of_week)],
                    "room_week_load": room_week_load[(room_id, week_number)],
                    "task_day_load": task_day_load[(task_id, week_number, day_of_week)],
                    "is_capacity_enough": int(capacity_enough),
                    "is_room_type_match": int(type_match),
                    "has_teacher_conflict": int(teacher_conflict),
                    "has_class_conflict": int(class_conflict),
                    "has_room_conflict": int(room_conflict),
                    "has_hard_conflict": int(has_hard_conflict),
                    "rule_score": rule_score,
                    "reject_reason": reject_reason(
                        teacher_conflict=teacher_conflict,
                        class_conflict=class_conflict,
                        room_conflict=room_conflict,
                        capacity_enough=capacity_enough,
                        type_match=type_match,
                    ),
                }
            )
    return rows


def build_features(rows: list[dict[str, Any]], schema: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    feature_columns = schema["feature_columns"]
    categorical_columns = schema["categorical_columns"]
    if "sample_weight" in feature_columns and "sample_weight" not in frame.columns:
        frame["sample_weight"] = 1.0
    missing_columns = [column for column in feature_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Candidate rows are missing required feature columns: {missing_columns}")

    features = frame[feature_columns].copy()
    for column in categorical_columns:
        features[column] = features[column].fillna("UNKNOWN").astype("category")
    numeric_columns = [column for column in feature_columns if column not in categorical_columns]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)
    return features


def load_policy(policy_name: str, custom_params: dict[str, float] | None = None) -> dict[str, float]:
    if policy_name not in POLICY_PROFILES:
        raise ValueError(f"Unknown policy: {policy_name}. Available: {sorted(POLICY_PROFILES.keys())}")
    merged = dict(POLICY_PROFILES[policy_name])
    if custom_params:
        for key in merged:
            if key in custom_params:
                merged[key] = float(custom_params[key])
    return merged


def shortlist_candidates(candidates: list[dict[str, Any]], pool_size: int, rng: random.Random, policy: dict[str, float]) -> list[dict[str, Any]]:
    if pool_size <= 0 or len(candidates) <= pool_size:
        return candidates
    legal_candidates = [candidate for candidate in candidates if int(candidate["has_hard_conflict"]) == 0]
    pool = legal_candidates if legal_candidates else candidates
    return sorted(
        pool,
        key=lambda row: (
            -int(row["has_hard_conflict"]),
            row["rule_score"],
            -row["scheme_day_load"],
            -row["room_day_load"],
            -row["room_week_load"],
            -row["task_day_load"],
            rng.random(),
        ),
        reverse=True,
    )[:pool_size]


def apply_selection_scores(
    candidates: list[dict[str, Any]],
    rng: random.Random,
    policy: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> None:
    for candidate in candidates:
        distribution_penalty = (
            candidate["scheme_day_load"] * policy["weekday_load_penalty"]
            + candidate["room_day_load"] * policy["room_day_load_penalty"]
            + candidate["room_week_load"] * policy["room_week_load_penalty"]
            + candidate["task_day_load"] * policy["task_day_load_penalty"]
        )
        weekend_penalty = (1 if int(candidate.get("is_weekend", 0)) else 0) * policy.get("weekend_penalty", 0.0)
        early_penalty = (1 if int(candidate.get("is_early_period", 0)) else 0) * policy["early_period_penalty"]
        late_penalty = (1 if int(candidate.get("is_late_period", 0)) else 0) * policy["late_period_penalty"]
        compact_bonus = candidate.get("scheme_day_load", 0) * policy["compact_bonus_weight"]

        stickiness_bonus = 0.0
        if task_classroom_id is not None:
            candidate_room = int(candidate.get("candidate_classroom_id", 0))
            if candidate_room == task_classroom_id:
                stickiness_bonus = float(policy.get("classroom_stickiness_bonus", 0.0))

        # Teacher profile penalty: teacher-specific constraints from Java orchestration.
        teacher_profile_penalty = 0.0
        teacher_profile_penalty_breakdown: list[dict[str, Any]] = []
        if teacher_id is not None and teacher_profiles is not None:
            profile = teacher_profiles.get(teacher_id)
            if profile is not None:
                unavailable_slots = profile.get("unavailable_slots", [])
                day = int(candidate.get("day_of_week", 0))
                period = int(candidate.get("period_index", 0))
                normalized_slots = {tuple(slot) for slot in normalize_unavailable_slots(unavailable_slots)}
                if (day, period) in normalized_slots:
                    penalty = float(profile.get("penalty_weight") or 0.05)
                    teacher_profile_penalty += penalty
                    teacher_profile_penalty_breakdown.append({
                        "type": "unavailable_slot",
                        "penalty": round(penalty, 4),
                        "day_of_week": day,
                        "period_index": period,
                        "reason": profile.get("reason") or "teacher unavailable slot",
                    })
                preferred_max = profile.get("max_weekly_hours")
                if preferred_max is not None:
                    current_week_hours = int(candidate.get("teacher_week_load", 0))
                    if current_week_hours + 1 > int(preferred_max):
                        penalty = 0.03
                        teacher_profile_penalty += penalty
                        teacher_profile_penalty_breakdown.append({
                            "type": "max_weekly_hours_exceeded",
                            "penalty": round(penalty, 4),
                            "teacher_week_load_before": current_week_hours,
                            "max_weekly_hours": int(preferred_max),
                            "reason": profile.get("reason") or "teacher preferred max weekly hours exceeded",
                        })

        random_jitter = rng.random() * policy["random_jitter"]
        candidate["distribution_penalty"] = round(distribution_penalty + weekend_penalty + early_penalty + late_penalty, 6)
        candidate["distribution_penalty_breakdown"] = {
            "weekday_load": round(candidate["scheme_day_load"] * policy["weekday_load_penalty"], 6),
            "room_day_load": round(candidate["room_day_load"] * policy["room_day_load_penalty"], 6),
            "room_week_load": round(candidate["room_week_load"] * policy["room_week_load_penalty"], 6),
            "task_day_load": round(candidate["task_day_load"] * policy["task_day_load_penalty"], 6),
            "weekend": round(weekend_penalty, 6),
            "early_period": round(early_penalty, 6),
            "late_period": round(late_penalty, 6),
        }
        candidate["compact_bonus"] = round(compact_bonus, 6)
        candidate["stickiness_bonus"] = round(stickiness_bonus, 6)
        candidate["teacher_profile_penalty"] = round(teacher_profile_penalty, 4)
        candidate["teacher_profile_penalty_breakdown"] = teacher_profile_penalty_breakdown
        candidate["random_jitter_value"] = round(random_jitter, 6)
        candidate["selection_score_formula"] = "predicted_score + rule_score*0.02 - distribution_penalty + compact_bonus + stickiness_bonus - teacher_profile_penalty + random_jitter"
        candidate["selection_score"] = max(
            0.0,
            float(candidate["predicted_score"])
            + float(candidate["rule_score"]) * 0.02
            - candidate["distribution_penalty"]
            + compact_bonus
            + stickiness_bonus
            - teacher_profile_penalty
            + random_jitter,
        )


def summarize_teacher_profile_penalty_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    penalized = [candidate for candidate in candidates if float(candidate.get("teacher_profile_penalty") or 0.0) > 0.0]
    if not penalized:
        return {
            "candidate_count": len(candidates),
            "penalized_candidate_count": 0,
            "legal_penalized_candidate_count": 0,
            "max_penalty": 0.0,
            "penalty_type_counts": {},
            "examples": [],
        }
    type_counts = Counter(
        item.get("type") or "unknown"
        for candidate in penalized
        for item in candidate.get("teacher_profile_penalty_breakdown", [])
    )
    examples = sorted(
        penalized,
        key=lambda row: float(row.get("teacher_profile_penalty") or 0.0),
        reverse=True,
    )[:5]
    return {
        "candidate_count": len(candidates),
        "penalized_candidate_count": len(penalized),
        "legal_penalized_candidate_count": sum(1 for candidate in penalized if int(candidate.get("has_hard_conflict") or 0) == 0),
        "max_penalty": round(max(float(candidate.get("teacher_profile_penalty") or 0.0) for candidate in penalized), 4),
        "penalty_type_counts": dict(type_counts),
        "examples": [
            {
                "classroom_id": candidate.get("candidate_classroom_id"),
                "time_slot_id": candidate.get("candidate_time_slot_id"),
                "week_number": candidate.get("week_number"),
                "day_of_week": candidate.get("day_of_week"),
                "period_index": candidate.get("period_index"),
                "has_hard_conflict": candidate.get("has_hard_conflict"),
                "teacher_profile_penalty": candidate.get("teacher_profile_penalty"),
                "breakdown": candidate.get("teacher_profile_penalty_breakdown") or [],
            }
            for candidate in examples
        ],
    }


def rank_candidates(
    *,
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    candidates: list[dict[str, Any]],
    rng: random.Random,
    policy: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    model_used = booster is not None and schema is not None
    if model_used:
        features = build_features(candidates, schema)
        predictions = np.clip(booster.predict(features), 0.0, 1.0)
        for candidate, predicted_score in zip(candidates, predictions):
            candidate["predicted_score"] = float(predicted_score)
        scores = [c["predicted_score"] for c in candidates]
        ml_logger.scoring_batch(
            task_id=int(candidates[0].get("teaching_task_id", 0)),
            candidate_count=len(candidates),
            score_mean=float(np.mean(scores)),
            score_std=float(np.std(scores)),
            score_min=float(np.min(scores)),
            score_max=float(np.max(scores)),
            model_used=True,
        )
    else:
        for candidate in candidates:
            candidate["predicted_score"] = float(candidate.get("rule_score") or 0.0)
        ml_logger.scoring_batch(
            task_id=int(candidates[0].get("teaching_task_id", 0)),
            candidate_count=len(candidates),
            score_mean=float(np.mean([c["predicted_score"] for c in candidates])),
            score_std=0.0,
            score_min=float(np.min([c["predicted_score"] for c in candidates])),
            score_max=float(np.max([c["predicted_score"] for c in candidates])),
            model_used=False,
        )
    apply_selection_scores(candidates, rng, policy, task_classroom_id, teacher_id, teacher_profiles)

    return sorted(
        candidates,
        key=lambda row: (
            row["selection_score"],
            -row["has_hard_conflict"],
            row["predicted_score"],
            row["rule_score"],
            -row["week_number"],
            -row["day_of_week"],
            -row["period_index"],
        ),
        reverse=True,
    )



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


def parse_int_set(raw_value: Any) -> set[int] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        values = [value.strip() for value in raw_value.split(",")]
    elif isinstance(raw_value, (list, tuple, set)):
        values = list(raw_value)
    else:
        values = [raw_value]
    parsed = {int(value) for value in values if str(value).strip()}
    return parsed or None


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


def policy_overrides_from_config(config: dict[str, Any]) -> dict[str, float]:
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
    return {target: float(config[source]) for source, target in mapping.items() if config.get(source) is not None}



def normalize_unavailable_slots(raw_slots: Any) -> list[list[int]]:
    normalized: list[list[int]] = []
    if not raw_slots:
        return normalized
    for slot in raw_slots:
        if isinstance(slot, (list, tuple)) and len(slot) >= 2:
            try:
                normalized.append([int(slot[0]), int(slot[1])])
            except (TypeError, ValueError):
                continue
    return sorted(normalized)


def normalize_teacher_penalties(raw: dict[str, Any]) -> dict[int, dict[str, Any]]:
    payload = raw.get("teacher_penalties", raw)
    penalties: dict[int, dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return penalties
    for teacher_key, value in payload.items():
        if not isinstance(value, dict):
            continue
        try:
            teacher_id = int(value.get("teacher_id") or teacher_key)
        except (TypeError, ValueError):
            continue
        penalties[teacher_id] = {
            "unavailable_slots": normalize_unavailable_slots(value.get("unavailable_slots")),
            "max_weekly_hours": int(value["max_weekly_hours"]) if value.get("max_weekly_hours") is not None else None,
            "penalty_weight": float(value.get("penalty_weight") or 0.05),
            "reason": str(value.get("reason") or value.get("note") or ""),
        }
    return penalties


def fallback_teacher_penalties(teacher_profiles: dict[int, dict[str, object]]) -> dict[int, dict[str, Any]]:
    return {
        teacher_id: {
            "unavailable_slots": normalize_unavailable_slots(profile.get("unavailable_slots")),
            "max_weekly_hours": profile.get("max_weekly_hours"),
            "penalty_weight": 0.05,
            "reason": "MySQL teacher_profile fallback",
        }
        for teacher_id, profile in teacher_profiles.items()
    }



def summarize_teacher_penalties(penalties: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "teacher_count": len(penalties),
        "teachers": [
            {
                "teacher_id": teacher_id,
                "unavailable_slots": penalty.get("unavailable_slots") or [],
                "max_weekly_hours": penalty.get("max_weekly_hours"),
                "penalty_weight": penalty.get("penalty_weight"),
                "reason": penalty.get("reason"),
            }
            for teacher_id, penalty in sorted(penalties.items())
        ],
    }


def load_teacher_penalties(path: Path) -> dict[int, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_teacher_penalties(payload)


def write_teacher_penalties(penalties: dict[int, dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"teacher_penalties": {str(key): value for key, value in sorted(penalties.items())}}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_teacher_profile_penalty_explanation(best: dict[str, Any]) -> str:
    breakdown = best.get("teacher_profile_penalty_breakdown") or []
    if not breakdown:
        return ""
    parts: list[str] = []
    for item in breakdown:
        penalty = item.get("penalty")
        reason = item.get("reason") or "教师画像约束"
        if item.get("type") == "unavailable_slot":
            parts.append(
                f"教师画像扣分 {penalty}：周{item.get('day_of_week')}第{item.get('period_index')}节命中不可用时间；{reason}"
            )
        elif item.get("type") == "max_weekly_hours_exceeded":
            parts.append(
                f"教师画像扣分 {penalty}：周课时 {item.get('teacher_week_load_before')}+1 超过偏好上限 {item.get('max_weekly_hours')}；{reason}"
            )
        else:
            parts.append(f"教师画像扣分 {penalty}：{reason}")
    return "；".join(parts)


def log_selected_candidate(task: dict[str, Any], fragment_index: int, best: dict[str, Any], candidate_count: int) -> None:
    candidate_stats = best.get("teacher_profile_candidate_stats") or {}
    if int(candidate_stats.get("penalized_candidate_count") or 0) > 0:
        log_chain("教师画像候选惩罚统计", {
            "teaching_task_id": task.get("teaching_task_id"),
            "teacher_id": task.get("teacher_id"),
            "teacher_name": task.get("teacher_name") or "",
            "fragment_index": fragment_index,
            "selected_penalty": best.get("teacher_profile_penalty"),
            "selected_penalty_breakdown": best.get("teacher_profile_penalty_breakdown") or [],
            **candidate_stats,
        })
    penalty_breakdown = best.get("teacher_profile_penalty_breakdown") or []
    if penalty_breakdown:
        log_chain("教师画像惩罚命中", {
            "teaching_task_id": task.get("teaching_task_id"),
            "teacher_id": task.get("teacher_id"),
            "teacher_name": task.get("teacher_name") or "",
            "fragment_index": fragment_index,
            "chosen_time": {
                "time_slot_id": best.get("candidate_time_slot_id"),
                "week_number": best.get("week_number"),
                "day_of_week": best.get("day_of_week"),
                "period_index": best.get("period_index"),
            },
            "total_penalty": best.get("teacher_profile_penalty"),
            "breakdown": penalty_breakdown,
        })
    log_chain("模型选择排课片段", {
        "teaching_task_id": task.get("teaching_task_id"),
        "teacher_id": task.get("teacher_id"),
        "teacher_name": task.get("teacher_name") or "",
        "fragment_index": fragment_index,
        "candidate_count": candidate_count,
        "chosen": {
            "classroom_id": best.get("candidate_classroom_id"),
            "time_slot_id": best.get("candidate_time_slot_id"),
            "week_number": best.get("week_number"),
            "day_of_week": best.get("day_of_week"),
            "period_index": best.get("period_index"),
            "has_hard_conflict": best.get("has_hard_conflict"),
            "reject_reason": best.get("reject_reason"),
        },
        "score": {
            "formula": best.get("selection_score_formula"),
            "selection_score": round(float(best.get("selection_score", 0.0)), 6),
            "predicted_score": round(float(best.get("predicted_score", 0.0)), 6),
            "rule_score": round(float(best.get("rule_score", 0.0)), 6),
            "distribution_penalty": best.get("distribution_penalty"),
            "distribution_penalty_breakdown": best.get("distribution_penalty_breakdown"),
            "teacher_profile_penalty": best.get("teacher_profile_penalty"),
            "teacher_profile_penalty_breakdown": best.get("teacher_profile_penalty_breakdown") or [],
            "teacher_profile_candidate_stats": best.get("teacher_profile_candidate_stats") or {},
            "compact_bonus": best.get("compact_bonus"),
            "stickiness_bonus": best.get("stickiness_bonus"),
            "random_jitter": best.get("random_jitter_value"),
        },
    })


def summarize_candidate_pool(raw_candidates: list[dict[str, Any]], pool_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    raw_hard_conflicts = sum(int(candidate.get("has_hard_conflict") or 0) for candidate in raw_candidates)
    selected_hard_conflicts = sum(int(candidate.get("has_hard_conflict") or 0) for candidate in pool_candidates)
    reject_reasons = Counter(
        str(candidate.get("reject_reason") or "ok")
        for candidate in raw_candidates
        if int(candidate.get("has_hard_conflict") or 0) == 1
    )
    selected_reject_reasons = Counter(
        str(candidate.get("reject_reason") or "ok")
        for candidate in pool_candidates
        if int(candidate.get("has_hard_conflict") or 0) == 1
    )
    return {
        "raw_candidate_count": len(raw_candidates),
        "raw_legal_candidate_count": len(raw_candidates) - raw_hard_conflicts,
        "raw_hard_candidate_count": raw_hard_conflicts,
        "selected_candidate_count": len(pool_candidates),
        "selected_legal_candidate_count": len(pool_candidates) - selected_hard_conflicts,
        "selected_hard_candidate_count": selected_hard_conflicts,
        "raw_reject_reason_top": dict(reject_reasons.most_common(5)),
        "selected_reject_reason_top": dict(selected_reject_reasons.most_common(5)),
    }


def build_candidate_pools(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    max_tasks: int | None,
    rng: random.Random,
    candidate_pool_size: int,
    candidate_top_n: int,
    policy: dict[str, float],
    exclude_weekends: bool,
) -> list[dict[str, Any]]:
    pools: list[dict[str, Any]] = []
    scoped_tasks = tasks[:max_tasks] if max_tasks is not None else tasks
    started_at = perf_counter()
    total_raw_candidates = 0
    total_legal_candidates = 0
    for task in scoped_tasks:
        task_started_at = perf_counter()
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        required_fragments = periods_needed(task)
        teacher_profile = teacher_profiles.get(teacher_id)
        task_diagnostic = diagnose_candidate_space(task, classrooms, time_slots, teacher_profile, exclude_weekends)
        if not task_diagnostic["has_any_feasible_candidate"]:
            task_diagnostic["missing_fragment_count"] = required_fragments
            task_diagnostic["raw_candidate_count"] = 0
            task_diagnostic["legal_candidate_count"] = 0
            task_diagnostic["selected_candidate_count"] = 0
            CANDIDATE_DIAGNOSTICS[task_id] = task_diagnostic
            log_chain("GA 排课前过滤不可行任务", {
                "teaching_task_id": task_id,
                "teacher_id": teacher_id,
                "required_fragments": required_fragments,
                "filtered_reason": task_diagnostic["filtered_reason"],
                "suggestions": task_diagnostic["suggestions"],
            })
            continue
        build_started_at = perf_counter()
        candidates = build_candidate_rows(
            task=task,
            classrooms=classrooms,
            time_slots=time_slots,
            selected_assignments=[],
            teacher_profile=teacher_profile,
            exclude_weekends=exclude_weekends,
        )
        add_timing("candidate_build_time", build_started_at)
        legal_candidates = [candidate for candidate in candidates if int(candidate.get("has_hard_conflict") or 0) == 0]
        total_raw_candidates += len(candidates)
        total_legal_candidates += len(legal_candidates)
        rank_started_at = perf_counter()
        ranked = rank_candidates(
            booster=booster,
            schema=schema,
            candidates=shortlist_candidates(legal_candidates, candidate_pool_size, rng, policy),
            rng=rng,
            policy=policy,
            task_classroom_id=task.get("bound_classroom_id"),
            teacher_id=teacher_id,
            teacher_profiles=teacher_profiles,
        )
        add_timing("rank_time", rank_started_at)
        pool_candidates = ranked[: max(1, min(candidate_top_n, len(ranked)))]
        base_summary = summarize_candidate_pool(candidates, pool_candidates)
        task_diagnostic.update({
            "raw_candidate_count": len(candidates),
            "legal_candidate_count": len(legal_candidates),
            "selected_candidate_count": len(pool_candidates),
            "missing_fragment_count": 0 if pool_candidates else required_fragments,
            "candidate_summary": base_summary,
        })
        CANDIDATE_DIAGNOSTICS[task_id] = task_diagnostic
        fragment_summaries: list[dict[str, Any]] = [
            {"fragment_index": fragment_index, **base_summary}
            for fragment_index in range(1, required_fragments + 1)
        ]
        if not pool_candidates:
            log_chain("GA 硬合法候选池为空", {
                "teaching_task_id": task_id,
                "teacher_id": teacher_id,
                "fragment_count": required_fragments,
                "required_capacity": task_diagnostic["required_capacity"],
                "available_classrooms": task_diagnostic["available_classrooms"],
                "filtered_reason": task_diagnostic["filtered_reason"],
                "has_any_available_classroom": task_diagnostic["has_any_available_classroom"],
                "has_any_feasible_candidate": task_diagnostic["has_any_feasible_candidate"],
                "suggestions": task_diagnostic["suggestions"],
                "raw_candidate_count": len(candidates),
                "raw_reject_reason_top": base_summary["raw_reject_reason_top"],
            })
        else:
            for fragment_index in range(1, required_fragments + 1):
                pools.append({
                    "task": task,
                    "task_id": task_id,
                    "teacher_id": teacher_id,
                    "class_group_ids": parse_id_tuple(task.get("class_group_ids")),
                    "fragment_index": fragment_index,
                    "candidates": pool_candidates,
                })
        if fragment_summaries:
            risky_fragments = [
                summary for summary in fragment_summaries
                if int(summary.get("selected_hard_candidate_count") or 0) > 0
                or int(summary.get("raw_legal_candidate_count") or 0) == 0
            ]
            log_chain("GA 候选池任务诊断", {
                "teaching_task_id": task_id,
                "teacher_id": teacher_id,
                "teacher_name": task.get("teacher_name") or "",
                "required_fragments": required_fragments,
                "class_group_ids": task.get("class_group_ids"),
                "required_room_type": effective_required_room_type(task),
                "avg_raw_legal_candidate_count": round(sum(item["raw_legal_candidate_count"] for item in fragment_summaries) / len(fragment_summaries), 2),
                "avg_selected_legal_candidate_count": round(sum(item["selected_legal_candidate_count"] for item in fragment_summaries) / len(fragment_summaries), 2),
                "fragments_with_selected_hard_candidates": sum(1 for item in fragment_summaries if int(item["selected_hard_candidate_count"]) > 0),
                "risky_fragments_sample": risky_fragments[:5],
                "build_duration_ms": round((perf_counter() - task_started_at) * 1000, 2),
            })
    skipped_tasks = [item["task_id"] for item in CANDIDATE_DIAGNOSTICS.values() if not item.get("has_any_feasible_candidate")]
    log_chain("GA 候选池全局诊断", {
        "pool_count": len(pools),
        "tasks": len(scoped_tasks),
        "raw_candidate_count": total_raw_candidates,
        "legal_candidate_count": total_legal_candidates,
        "candidate_top_n": candidate_top_n,
        "candidate_pool_size": candidate_pool_size,
        "build_duration_ms": round((perf_counter() - started_at) * 1000, 2),
        "skipped_infeasible_tasks": skipped_tasks,
    })
    ml_logger.ga_pool_diagnostics({
        "pool_count": len(pools),
        "tasks": len(scoped_tasks),
        "raw_candidate_count": total_raw_candidates,
        "legal_candidate_count": total_legal_candidates,
        "candidate_top_n": candidate_top_n,
        "candidate_pool_size": candidate_pool_size,
        "build_duration_ms": round((perf_counter() - started_at) * 1000, 2),
        "skipped_infeasible_tasks": skipped_tasks,
    })
    return pools


def conflicts_with_occupied(candidate: dict[str, Any], pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]]) -> bool:
    time_slot_id = int(candidate["candidate_time_slot_id"])
    classroom_id = int(candidate["candidate_classroom_id"])
    if int(candidate.get("has_hard_conflict") or 0) == 1:
        return True
    if (pool["teacher_id"], time_slot_id) in occupied["teacher_slot"]:
        return True
    if (classroom_id, time_slot_id) in occupied["room_slot"]:
        return True
    return any((class_group_id, time_slot_id) in occupied["class_slot"] for class_group_id in pool["class_group_ids"])


def occupy_candidate(candidate: dict[str, Any], pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]]) -> None:
    time_slot_id = int(candidate["candidate_time_slot_id"])
    classroom_id = int(candidate["candidate_classroom_id"])
    occupied["teacher_slot"].add((pool["teacher_id"], time_slot_id))
    occupied["room_slot"].add((classroom_id, time_slot_id))
    for class_group_id in pool["class_group_ids"]:
        occupied["class_slot"].add((class_group_id, time_slot_id))


def empty_occupied() -> dict[str, set[tuple[int, int]]]:
    return {"teacher_slot": set(), "room_slot": set(), "class_slot": set()}


def choose_feasible_gene(pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]], rng: random.Random) -> int | None:
    feasible_indexes = [
        index for index, candidate in enumerate(pool["candidates"])
        if not conflicts_with_occupied(candidate, pool, occupied)
    ]
    if not feasible_indexes:
        return None
    preferred = feasible_indexes[: min(10, len(feasible_indexes))]
    return rng.choice(preferred)


def repair_individual(individual: list[int], pools: list[dict[str, Any]], rng: random.Random, log_unresolved: bool = False) -> list[int]:
    repaired = individual[:]
    occupied = empty_occupied()
    order = list(range(len(pools)))
    order.sort(key=lambda index: (len(pools[index]["candidates"]), rng.random()))
    unresolved: list[int] = []
    for index in order:
        pool = pools[index]
        current_gene = repaired[index]
        current_candidate = pool["candidates"][current_gene]
        if not conflicts_with_occupied(current_candidate, pool, occupied):
            occupy_candidate(current_candidate, pool, occupied)
            continue
        replacement = choose_feasible_gene(pool, occupied, rng)
        if replacement is None:
            unresolved.append(index)
            continue
        repaired[index] = replacement
        occupy_candidate(pool["candidates"][replacement], pool, occupied)
    if unresolved and log_unresolved:
        log_chain("GA repair 未能完全消除冲突", {"unresolved_fragment_count": len(unresolved), "sample_indexes": unresolved[:10]})
    return repaired


def random_individual(pools: list[dict[str, Any]], rng: random.Random) -> list[int]:
    raw = [rng.randrange(len(pool["candidates"])) for pool in pools]
    return repair_individual(raw, pools, rng)


def individual_rows(individual: list[int], pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence, (gene, pool) in enumerate(zip(individual, pools), start=1):
        candidate = pool["candidates"][gene]
        task = pool["task"]
        penalty_breakdown = candidate.get("teacher_profile_penalty_breakdown") or []
        rows.append({
            "sequence": sequence,
            "teaching_task_id": pool["task_id"],
            "teacher_id": pool["teacher_id"],
            "teacher_name": task.get("teacher_name") or "",
            "fragment_index": pool["fragment_index"],
            "classroom_id": int(candidate["candidate_classroom_id"]),
            "time_slot_id": int(candidate["candidate_time_slot_id"]),
            "week_number": int(candidate["week_number"]),
            "day_of_week": int(candidate["day_of_week"]),
            "period_index": int(candidate["period_index"]),
            "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 4),
            "rule_score": candidate.get("rule_score") or 0.0,
            "has_hard_conflict": candidate.get("has_hard_conflict") or 0,
            "reject_reason": candidate.get("reject_reason") or "",
            "teacher_profile_penalty": candidate.get("teacher_profile_penalty") or 0.0,
            "teacher_profile_penalty_explanation": format_teacher_profile_penalty_explanation(candidate),
            "teacher_profile_penalty_breakdown": json.dumps(penalty_breakdown, ensure_ascii=False),
        })
    return rows


def individual_assignments(individual: list[int], pools: list[dict[str, Any]]) -> list[PseudoAssignment]:
    assignments: list[PseudoAssignment] = []
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        assignments.append(PseudoAssignment(
            task_id=pool["task_id"],
            teacher_id=pool["teacher_id"],
            class_group_ids=pool["class_group_ids"],
            classroom_id=int(candidate["candidate_classroom_id"]),
            time_slot_id=int(candidate["candidate_time_slot_id"]),
            week_number=int(candidate["week_number"]),
            day_of_week=int(candidate["day_of_week"]),
            period_index=int(candidate["period_index"]),
        ))
    return assignments


def summarize_individual_conflict_hotspots(individual: list[int], pools: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    teacher_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    room_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    class_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    candidate_conflicts: list[dict[str, Any]] = []
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        item = {
            "task_id": pool["task_id"],
            "teacher_id": pool["teacher_id"],
            "fragment_index": pool["fragment_index"],
            "classroom_id": int(candidate["candidate_classroom_id"]),
            "time_slot_id": int(candidate["candidate_time_slot_id"]),
            "week_number": int(candidate["week_number"]),
            "day_of_week": int(candidate["day_of_week"]),
            "period_index": int(candidate["period_index"]),
            "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 6),
            "rule_score": round(float(candidate.get("rule_score") or 0.0), 6),
            "reject_reason": candidate.get("reject_reason") or "",
        }
        teacher_slot.setdefault((pool["teacher_id"], item["time_slot_id"]), []).append(item)
        room_slot.setdefault((item["classroom_id"], item["time_slot_id"]), []).append(item)
        for class_group_id in pool["class_group_ids"]:
            class_slot.setdefault((class_group_id, item["time_slot_id"]), []).append(item)
        if int(candidate.get("has_hard_conflict") or 0) == 1:
            candidate_conflicts.append(item)

    def top_duplicates(index: dict[tuple[int, int], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        duplicates = [
            {"key": key, "count": len(items), "items": items[:5]}
            for key, items in index.items()
            if len(items) > 1
        ]
        duplicates.sort(key=lambda row: row["count"], reverse=True)
        return duplicates[:limit]

    return {
        "candidate_conflicts_sample": candidate_conflicts[:limit],
        "teacher_slot_duplicates": top_duplicates(teacher_slot),
        "room_slot_duplicates": top_duplicates(room_slot),
        "class_slot_duplicates": top_duplicates(class_slot),
    }


def evaluate_individual(
    individual: list[int],
    pools: list[dict[str, Any]],
    *,
    predicted_score_weight: float,
    rule_score_weight: float,
    hard_conflict_penalty: float,
    teacher_profile_penalty_scale: float,
    distribution_penalty_scale: float,
    classroom_stickiness_weight: float,
    compact_bonus_weight: float,
) -> dict[str, Any]:
    if not individual:
        return {"fitness": -1_000_000.0}
    teacher_slot: Counter[tuple[int, int]] = Counter()
    class_slot: Counter[tuple[int, int]] = Counter()
    room_slot: Counter[tuple[int, int]] = Counter()
    day_load: Counter[tuple[int, int]] = Counter()
    task_day_load: Counter[tuple[int, int, int]] = Counter()
    task_rooms: dict[int, set[int]] = {}
    predicted_total = 0.0
    rule_total = 0.0
    candidate_hard_conflicts = 0
    teacher_profile_penalty_total = 0.0

    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        teacher_id = pool["teacher_id"]
        time_slot_id = int(candidate["candidate_time_slot_id"])
        room_id = int(candidate["candidate_classroom_id"])
        week_number = int(candidate["week_number"])
        day_of_week = int(candidate["day_of_week"])
        predicted_total += float(candidate.get("predicted_score") or 0.0)
        rule_total += float(candidate.get("rule_score") or 0.0)
        candidate_hard_conflicts += int(candidate.get("has_hard_conflict") or 0)
        teacher_profile_penalty_total += float(candidate.get("teacher_profile_penalty") or 0.0)
        teacher_slot[(teacher_id, time_slot_id)] += 1
        room_slot[(room_id, time_slot_id)] += 1
        for class_group_id in pool["class_group_ids"]:
            class_slot[(class_group_id, time_slot_id)] += 1
        day_load[(week_number, day_of_week)] += 1
        task_day_load[(pool["task_id"], week_number, day_of_week)] += 1
        task_rooms.setdefault(pool["task_id"], set()).add(room_id)

    teacher_slot_conflicts = sum(count - 1 for count in teacher_slot.values() if count > 1)
    room_slot_conflicts = sum(count - 1 for count in room_slot.values() if count > 1)
    class_slot_conflicts = sum(count - 1 for count in class_slot.values() if count > 1)
    duplicate_conflicts = teacher_slot_conflicts + room_slot_conflicts + class_slot_conflicts
    hard_conflicts = candidate_hard_conflicts + duplicate_conflicts
    distribution_penalty = sum(max(0, count - 4) for count in day_load.values())
    distribution_penalty += sum(max(0, count - 2) for count in task_day_load.values())
    classroom_switches = sum(max(0, len(room_ids) - 1) for room_ids in task_rooms.values())
    compact_bonus = sum(max(0, count - 1) for count in task_day_load.values())

    size = len(individual)
    avg_predicted = predicted_total / size
    avg_rule = rule_total / size
    soft_score = (
        avg_predicted * predicted_score_weight
        + avg_rule * rule_score_weight
        - teacher_profile_penalty_total * teacher_profile_penalty_scale
        - distribution_penalty * distribution_penalty_scale
        - classroom_switches * classroom_stickiness_weight
        + compact_bonus * compact_bonus_weight
    )
    fitness = -hard_conflicts * hard_conflict_penalty + soft_score
    return {
        "fitness": round(fitness, 6),
        "soft_score": round(soft_score, 6),
        "avg_predicted_score": round(avg_predicted, 6),
        "avg_rule_score": round(avg_rule, 6),
        "hard_conflict_count": hard_conflicts,
        "candidate_hard_conflict_count": candidate_hard_conflicts,
        "duplicate_conflict_count": duplicate_conflicts,
        "teacher_slot_conflict_count": teacher_slot_conflicts,
        "room_slot_conflict_count": room_slot_conflicts,
        "class_slot_conflict_count": class_slot_conflicts,
        "teacher_profile_penalty_total": round(teacher_profile_penalty_total, 6),
        "distribution_penalty": distribution_penalty,
        "classroom_switches": classroom_switches,
        "compact_bonus": compact_bonus,
    }


def tournament_select(scored: list[dict[str, Any]], tournament_size: int, rng: random.Random) -> list[int]:
    contenders = rng.sample(scored, k=min(tournament_size, len(scored)))
    return max(contenders, key=lambda item: item["metrics"]["fitness"])["individual"][:]


def crossover(parent_a: list[int], parent_b: list[int], pools: list[dict[str, Any]], rng: random.Random) -> list[int]:
    task_ids = sorted({pool["task_id"] for pool in pools})
    inherited_from_a = set(rng.sample(task_ids, k=max(1, len(task_ids) // 2))) if task_ids else set()
    return [parent_a[index] if pools[index]["task_id"] in inherited_from_a else parent_b[index] for index in range(len(pools))]


def mutate(individual: list[int], pools: list[dict[str, Any]], mutation_rate: float, rng: random.Random) -> None:
    for index, pool in enumerate(pools):
        if rng.random() < mutation_rate and len(pool["candidates"]) > 1:
            individual[index] = rng.randrange(len(pool["candidates"]))


def evolve_population(
    pools: list[dict[str, Any]],
    rng: random.Random,
    *,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    fitness_kwargs: dict[str, float],
) -> list[dict[str, Any]]:
    init_started_at = perf_counter()
    population = [random_individual(pools, rng) for _ in range(population_size)]
    add_timing("ga_init_time", init_started_at)
    evolution_started_at = perf_counter()
    scored: list[dict[str, Any]] = []
    for generation in range(1, generations + 1):
        scored = [
            {"individual": individual, "metrics": evaluate_individual(individual, pools, **fitness_kwargs)}
            for individual in population
        ]
        scored.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
        if generation == 1 or generation == generations or generation % 10 == 0:
            m = scored[0]["metrics"]
            log_chain("GA 迭代进度", {
                "generation": generation,
                "best_fitness": m["fitness"],
                "best_hard_conflicts": m.get("hard_conflict_count"),
                "candidate_hard_conflicts": m.get("candidate_hard_conflict_count"),
                "teacher_slot_conflicts": m.get("teacher_slot_conflict_count"),
                "room_slot_conflicts": m.get("room_slot_conflict_count"),
                "class_slot_conflicts": m.get("class_slot_conflict_count"),
            })
            ml_logger.ga_iteration(
                generation=generation,
                best_fitness=m["fitness"],
                hard_conflicts=m.get("hard_conflict_count", 0),
                candidate_hard_conflicts=m.get("candidate_hard_conflict_count", 0),
                teacher_slot_conflicts=m.get("teacher_slot_conflict_count", 0),
                room_slot_conflicts=m.get("room_slot_conflict_count", 0),
                class_slot_conflicts=m.get("class_slot_conflict_count", 0),
            )
        next_population = [item["individual"][:] for item in scored[: max(1, min(elite_size, len(scored)))]]
        while len(next_population) < population_size:
            parent_a = tournament_select(scored, tournament_size, rng)
            parent_b = tournament_select(scored, tournament_size, rng)
            child = crossover(parent_a, parent_b, pools, rng)
            mutate(child, pools, mutation_rate, rng)
            repair_started_at = perf_counter()
            next_population.append(repair_individual(child, pools, rng))
            add_timing("repair_time", repair_started_at)
        population = next_population
    add_timing("ga_evolution_time", evolution_started_at)
    scored = [
        {"individual": individual, "metrics": evaluate_individual(individual, pools, **fitness_kwargs)}
        for individual in population
    ]
    scored.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
    return scored


def generate_scheme(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    max_tasks: int | None,
    rng: random.Random,
    candidate_pool_size: int,
    candidate_top_n: int,
    policy: dict[str, float],
    exclude_weekends: bool = False,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
    elite_size: int = DEFAULT_ELITE_SIZE,
    tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    fitness_kwargs: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list[PseudoAssignment], dict[str, Any]]:
    pools = build_candidate_pools(
        tasks=tasks,
        classrooms=classrooms,
        time_slots=time_slots,
        teacher_profiles=teacher_profiles,
        booster=booster,
        schema=schema,
        max_tasks=max_tasks,
        rng=rng,
        candidate_pool_size=candidate_pool_size,
        candidate_top_n=candidate_top_n,
        policy=policy,
        exclude_weekends=exclude_weekends,
    )
    if not pools:
        raise ValueError("GA candidate pools are empty")
    effective_fitness_kwargs = fitness_kwargs or {}
    scored = evolve_population(
        pools,
        rng,
        population_size=population_size,
        generations=generations,
        elite_size=elite_size,
        tournament_size=tournament_size,
        mutation_rate=mutation_rate,
        fitness_kwargs=effective_fitness_kwargs,
    )
    best = scored[0]
    repair_started_at = perf_counter()
    best["individual"] = repair_individual(best["individual"], pools, rng, log_unresolved=True)
    add_timing("repair_time", repair_started_at)
    validate_started_at = perf_counter()
    best["metrics"] = evaluate_individual(best["individual"], pools, **effective_fitness_kwargs)
    add_timing("validate_time", validate_started_at)
    rows = individual_rows(best["individual"], pools)
    assignments = individual_assignments(best["individual"], pools)
    metrics = {**best["metrics"], "candidate_pool_count": len(pools)}
    log_chain("GA 最优方案", metrics)
    ml_logger.ga_summary(metrics)
    hotspots = summarize_individual_conflict_hotspots(best["individual"], pools)
    log_chain("GA 最优方案冲突热点", hotspots)
    ml_logger.ga_conflict_hotspots(hotspots)
    return rows, assignments, metrics


def write_scheme(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_scheme(rows: list[dict[str, Any]], tasks: list[dict[str, Any]], max_tasks: int | None) -> dict[str, Any]:
    scoped_tasks = tasks[:max_tasks] if max_tasks is not None else tasks
    expected_fragments = sum(periods_needed(task) for task in scoped_tasks)
    actual_fragments = len(rows)
    conflict_rows = [row for row in rows if int(row["has_hard_conflict"]) == 1]
    avg_predicted_score = sum(float(row["predicted_score"]) for row in rows) / actual_fragments if rows else 0.0
    avg_rule_score = sum(float(row["rule_score"]) for row in rows) / actual_fragments if rows else 0.0
    return {
        "tasks": len(scoped_tasks),
        "expected_fragments": expected_fragments,
        "generated_fragments": actual_fragments,
        "hard_conflict_fragments": len(conflict_rows),
        "avg_predicted_score": round(avg_predicted_score, 6),
        "avg_rule_score": round(avg_rule_score, 6),
    }


def summarize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "fitness": metrics.get("fitness"),
        "hard_conflict_count": metrics.get("hard_conflict_count"),
        "candidate_hard_conflict_count": metrics.get("candidate_hard_conflict_count"),
        "teacher_slot_conflict_count": metrics.get("teacher_slot_conflict_count"),
        "room_slot_conflict_count": metrics.get("room_slot_conflict_count"),
        "class_slot_conflict_count": metrics.get("class_slot_conflict_count"),
        "teacher_profile_penalty_total": metrics.get("teacher_profile_penalty_total"),
        "distribution_penalty": metrics.get("distribution_penalty"),
        "classroom_switches": metrics.get("classroom_switches"),
        "candidate_pool_count": metrics.get("candidate_pool_count"),
    }


def print_summary(rows: list[dict[str, Any]], tasks: list[dict[str, Any]], max_tasks: int | None) -> None:
    summary = summarize_scheme(rows, tasks, max_tasks)
    lines = [
        "Generated model-driven scheduling demo",
        f"Tasks: {summary['tasks']}",
        f"Expected fragments: {summary['expected_fragments']}",
        f"Generated fragments: {summary['generated_fragments']}",
        f"Hard-conflict fragments: {summary['hard_conflict_fragments']}",
        f"Average predicted score: {summary['avg_predicted_score']:.4f}",
        f"Average rule score: {summary['avg_rule_score']:.4f}",
    ]
    for l in lines:
        print(l)
        ml_logger.service.info("SCHEDULE %s", l)


def write_summary(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_candidate_diagnostics(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = sorted(CANDIDATE_DIAGNOSTICS.values(), key=lambda item: item["task_id"])
    payload = {
        "summary": {
            "task_count": len(diagnostics),
            "infeasible_task_count": sum(1 for item in diagnostics if not item.get("has_any_feasible_candidate")),
            "missing_fragment_count": sum(int(item.get("missing_fragment_count") or 0) for item in diagnostics),
            "skipped_infeasible_task_ids": [item["task_id"] for item in diagnostics if not item.get("has_any_feasible_candidate")],
            "timings_ms": {key: round(value, 3) for key, value in RUN_TIMINGS.items()},
        },
        "tasks": diagnostics,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── LLM Teacher Penalty Parser ────────────────────────────────────────

def _llm_config_from_env() -> dict[str, str] | None:
    """Read LLM API config from environment (same env vars Java uses)."""
    import os
    api_key = os.environ.get("OPENAI_CHAT_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "base_url": (
            os.environ.get("OPENAI_CHAT_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ),
        "model": (
            os.environ.get("OPENAI_CHAT_MODEL")
            or "deepseek-v4-pro"
        ),
    }


def _call_llm(prompt: str, config: dict[str, str]) -> str:
    """Call an OpenAI-compatible chat API with the given prompt."""
    import json as _jenc
    import urllib.request as _ur

    url = f"{config['base_url'].rstrip('/')}/chat/completions"
    body = _jenc.dumps({
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4096,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }

    req = _ur.Request(url, data=body, headers=headers, method="POST")
    try:
        with _ur.urlopen(req, timeout=60) as resp:
            result = _jenc.loads(resp.read().decode("utf-8"))
        choices = result.get("choices", [])
        if not choices:
            raise ValueError(f"LLM response has no choices: {result}")
        content = choices[0]["message"]["content"]
        log_chain("LLM API 调用成功", {"model": config.get("model"), "input_tokens": len(prompt), "response_length": len(content)})
        return content
    except Exception as exc:
        log_chain("LLM API 调用失败", {"model": config.get("model"), "error": str(exc)})
        raise ValueError(f"LLM API call failed: {exc}") from exc


def _parse_teacher_penalties_via_llm(
    teacher_profiles: dict[int, dict[str, Any]],
    llm_config: dict[str, str],
) -> dict[int, dict[str, Any]]:
    """Use LLM to parse teacher profile texts into structured GA penalties.

    Falls back gracefully on error — logs warning and returns empty dict.
    """
    import traceback as _tb

    # Build prompt: list all teachers with their raw profile text
    teacher_entries = []
    for tid, profile in sorted(teacher_profiles.items()):
        text = profile.get("vector_text") or profile.get("raw_text") or ""
        if not text.strip():
            continue
        teacher_entries.append(f"Teacher ID {tid}:\n{text.strip()}")

    if not teacher_entries:
        log_chain("LLM 教师罚秒析: 无有效教师文本，跳过")
        return {}

    prompt = (
        "你是一个排课专家。请从以下教师档案中提取排课约束条件。\n"
        "每位教师的档案可能包含：可用时间、不可用时间、每周课时上限、\n"
        "特殊备注（如身体情况、教研活动、毕业设计指导等）。\n\n"
        "请为每位教师输出 JSON，格式如下：\n"
        '{\n'
        '  "teacher_id": {\n'
        '    "unavailable_slots": [[day, period], ...],\n'
        '    "max_weekly_hours": 12,\n'
        '    "penalty_weight": 0.08,\n'
        '    "reason": "原因简述"\n'
        '  }\n'
        '}\n\n'
        "注意：\n"
        "- 星期用 1-7（周一=1，周日=7），节次用 1-8\n"
        "- 没有约束的字段设为 null\n"
        "- penalty_weight 取值 0.02~0.15，一般约束 0.05，特殊 0.10~0.15\n"
        "- 只在 JSON 中包含明确提到的约束，不要凭空编造\n"
        "- 只输出 JSON，不要解释\n\n"
        + "\n---\n".join(teacher_entries)
    )

    try:
        response = _call_llm(prompt, llm_config)
        parsed = json.loads(response)
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned non-dict: {response[:200]}")

        # Validate and normalize
        result: dict[int, dict[str, Any]] = {}
        for tid_str, penalty in parsed.items():
            try:
                tid = int(tid_str)
            except (TypeError, ValueError):
                continue
            if not isinstance(penalty, dict):
                continue
            result[tid] = {
                "unavailable_slots": _normalize_llm_slots(penalty.get("unavailable_slots")),
                "max_weekly_hours": (int(penalty["max_weekly_hours"])
                                     if penalty.get("max_weekly_hours") is not None else None),
                "penalty_weight": float(penalty.get("penalty_weight", 0.05)),
                "reason": str(penalty.get("reason") or ""),
            }

        log_chain("LLM 教师罚秒析完成",
                  {"teacher_count": len(result), "teachers": list(result.keys())})
        return result

    except Exception as exc:
        log_chain("LLM 教师罚秒析失败", {"error": str(exc), "traceback": _tb.format_exc()})
        return {}


def _normalize_llm_slots(raw: Any) -> list[list[int]]:
    """Normalize LLM-output unavailable slots [[day, period], ...]."""
    if not raw or not isinstance(raw, (list, tuple)):
        return []
    normalized: list[list[int]] = []
    for slot in raw:
        if isinstance(slot, (list, tuple)) and len(slot) >= 2:
            try:
                d, p = int(slot[0]), int(slot[1])
                if 1 <= d <= 7 and 1 <= p <= 8:
                    normalized.append([d, p])
            except (TypeError, ValueError):
                continue
    return sorted(normalized)


def run_ga_pipeline_by_task(
    task_id: int,
    db_config: dict[str, str] | None = None,
    *,
    model_path: Path = MODEL_PATH,
    schema_path: Path = FEATURE_SCHEMA_PATH,
    variant_count: int = 3,
    candidate_pool_size: int = DEFAULT_CANDIDATE_POOL_SIZE,
    candidate_top_n: int = DEFAULT_CANDIDATE_TOP_N,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
    elite_size: int = DEFAULT_ELITE_SIZE,
    tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    exclude_weekends: bool = False,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Run GA pipeline driven by a task_id — reads everything from DB.

    This is the entry point for the FastAPI async endpoint. Java only needs
    to pass task_id; Python looks up teaching tasks, generation config,
    teacher penalties, etc. from the database directly.
    """
    from generate_training_samples import (
        connect,
        fetch_allocation_task,
        fetch_task_teaching_task_ids,
        fetch_generation_config,
        fetch_tasks,
        fetch_classrooms,
        fetch_time_slots,
        fetch_teacher_profiles,
        load_db_config,
    )

    from datetime import datetime as _dt
    ROOT_DIR = Path(__file__).resolve().parents[1]
    timestamp = _dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    output_dir = ROOT_DIR / "data" / "generated_schemes" / f"task_{task_id}_{timestamp}"

    effective_db = db_config or load_db_config()
    with connect(effective_db) as connection:
        # 1. Verify task exists
        log_chain("DB: 查询排课任务", {"task_id": task_id})
        allocation_task = fetch_allocation_task(connection, task_id)
        if allocation_task is None:
            raise ValueError(f"Allocation task {task_id} not found")
        log_chain("DB: 排课任务存在", {"task_id": task_id, "name": allocation_task.get("name")})

        # 2. Get bound teaching task IDs
        log_chain("DB: 查询教学任务关联", {"task_id": task_id})
        teaching_task_ids = fetch_task_teaching_task_ids(connection, task_id)
        if not teaching_task_ids:
            raise ValueError(f"No teaching tasks bound to allocation task {task_id}")
        log_chain("DB: 教学任务关联", {"task_id": task_id, "teaching_task_count": len(teaching_task_ids)})

        # 3. Get generation config (optional — uses defaults if missing)
        log_chain("DB: 查询生成配置", {"task_id": task_id})
        raw_config = fetch_generation_config(connection, task_id)
        log_chain("DB: 生成配置", {"task_id": task_id, "found": raw_config is not None})

        # 4. Load base data
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)
        log_chain("DB: 基础数据加载完成", {
            "tasks": len(tasks), "classrooms": len(classrooms),
            "time_slots": len(time_slots), "teacher_profiles": len(teacher_profiles),
        })

    # Build generation config JSON (mirrors Java's toGenerationConfigJson)
    generation_config_json = _build_generation_config_json(raw_config) if raw_config else None
    if raw_config and raw_config.get("scheme_count") is not None:
        variant_count = int(raw_config.get("scheme_count"))

    # Filter to task's teaching tasks
    teaching_task_ids_str = ",".join(str(tid) for tid in teaching_task_ids)

    # Try LLM parsing of teacher profiles first, fallback to rule-based
    llm_config = _llm_config_from_env()
    if llm_config:
        log_chain("尝试 LLM 解析教师画像惩罚", {"teacher_count": len(teacher_profiles)})
        llm_penalties = _parse_teacher_penalties_via_llm(teacher_profiles, llm_config)
    else:
        log_chain("LLM 未配置（缺少 API_KEY），使用规则回退",
                  {"checked_vars": ["OPENAI_CHAT_API_KEY", "OPENAI_API_KEY"]})
        llm_penalties = {}

    # Merge: LLM results override fallback for teachers that were parsed
    teacher_penalties = fallback_teacher_penalties(teacher_profiles)
    for tid, llm_p in llm_penalties.items():
        if tid in teacher_penalties:
            teacher_penalties[tid].update(llm_p)
        else:
            teacher_penalties[tid] = llm_p

    # Write teacher penalties to disk for the pipeline
    teacher_penalties_path = output_dir / "teacher_penalties.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_teacher_penalties(teacher_penalties, teacher_penalties_path)

    seed = random_seed if random_seed is not None else int(task_id % 1_000_000)
    args = argparse.Namespace(
        model=model_path,
        schema=schema_path,
        output=output_dir / "scheme_001.csv",
        output_dir=output_dir,
        max_tasks=None,
        variant_count=variant_count,
        random_seed=seed,
        policy=DEFAULT_POLICY,
        policy_params=None,
        generation_config=generation_config_json,
        teacher_penalties=teacher_penalties_path,
        teaching_task_ids=teaching_task_ids_str,
        start_week=None,
        end_week=None,
        exclude_weekends=exclude_weekends,
        candidate_pool_size=candidate_pool_size,
        candidate_top_n=candidate_top_n,
        population_size=population_size,
        generations=generations,
        elite_size=elite_size,
        tournament_size=tournament_size,
        mutation_rate=mutation_rate,
        predicted_score_weight=DEFAULT_PREDICTED_SCORE_WEIGHT,
        rule_score_weight=DEFAULT_RULE_SCORE_WEIGHT,
        hard_conflict_penalty=DEFAULT_HARD_CONFLICT_PENALTY,
        teacher_profile_penalty_scale=50.0,
        distribution_penalty_scale=5.0,
        classroom_stickiness_weight=5.0,
        compact_bonus_weight=0.0,
        log_file=PROJECT_LOG_DIR / f"python-ga-{output_dir.name}.log",
    )
    result = run_ga_pipeline(args)

    # Persist schemes + detect conflicts directly to MySQL
    try:
        from persist_scheme import (
            reject_old_candidates, insert_scheme, insert_item,
            insert_conflict, update_scheme_conflict_state,
            detect_conflicts, summarize_violations,
        )

        from generate_training_samples import connect, load_db_config
        with connect(load_db_config()) as conn:
            reject_old_candidates(conn, task_id)
            log_chain("DB: 旧候选方案已标记为 REJECTED")

            schemes_data = result.get("schemes", [])
            all_item_rows = result.get("item_rows", [])
            for idx, (scheme_info, item_rows) in enumerate(zip(schemes_data, all_item_rows)):
                scheme_db = {
                    "scheme_name": scheme_info.get("scheme_name", f"方案 {idx + 1:03d}"),
                    "summary": summarize_scheme(item_rows, [], None),
                    "scheme_score": None,
                    "evaluation_summary": None,
                    "policy": DEFAULT_POLICY,
                    "model_version": "v1",
                    "conflict_summary": None,
                    "valid": True,
                }
                scheme_id = insert_scheme(conn, task_id, scheme_db)
                log_chain("DB: 方案已落库", {"scheme_id": scheme_id, "name": scheme_db["scheme_name"]})

                # Insert items
                item_ids: list[int] = []
                for row in item_rows:
                    item_data = {
                        "teaching_task_id": int(row["teaching_task_id"]),
                        "classroom_id": int(row["classroom_id"]),
                        "time_slot_id": int(row["time_slot_id"]),
                        "valid": True,
                        "conflict_message": row.get("reject_reason") or None,
                    }
                    item_id = insert_item(conn, scheme_id, item_data)
                    item_ids.append(item_id)

                # Detect conflicts from inserted items
                item_records = [
                    {"id": iid, "teaching_task_id": int(r["teaching_task_id"]),
                     "classroom_id": int(r["classroom_id"]), "time_slot_id": int(r["time_slot_id"])}
                    for iid, r in zip(item_ids, item_rows)
                ]
                violations = detect_conflicts(item_records, conn)
                for v in violations:
                    insert_conflict(conn, v)

                conflict_summary = summarize_violations(violations)
                valid = len(violations) == 0
                update_scheme_conflict_state(conn, scheme_id, valid, conflict_summary)
                log_chain("DB: 方案冲突检测完成",
                          {"scheme_id": scheme_id, "valid": valid, "violations": len(violations)})

        log_chain("DB: 全部方案持久化完成", {"task_id": task_id, "scheme_count": len(schemes_data)})
    except Exception as exc:
        import traceback as _tb
        log_chain("DB: 方案持久化失败（不影响 CSV 产物）",
                  {"error": str(exc), "traceback": _tb.format_exc()})

    return result


def _build_generation_config_json(raw_config: dict[str, Any]) -> str:
    """Convert DB generation config row to the JSON format Java used to send."""
    import json as _json
    config = {
        "allowedWeeks": str(raw_config.get("allowed_weeks", "")),
        "allowedWeekdays": str(raw_config.get("allowed_weekdays", "")),
        "allowedPeriods": str(raw_config.get("allowed_periods", "")),
        "schemeCount": int(raw_config.get("scheme_count", 3)),
        "teacherProfilePenaltyScale": float(raw_config.get("teacher_profile_penalty_scale", 50.0)),
        "distributionPenaltyScale": float(raw_config.get("distribution_penalty_scale", 5.0)),
        "classroomStickinessWeight": float(raw_config.get("classroom_stickiness_weight", 5.0)),
        "compactBonusWeight": float(raw_config.get("compact_bonus_weight", 0.0)),
    }
    # Optional fine-grained weights if they exist
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
        val = raw_config.get(src)
        if val is not None:
            config[dst] = float(val)
    return _json.dumps(config, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scheduling schemes with GA + LightGBM.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Trained LightGBM model path.")
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH, help="Feature schema JSON path.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Single generated scheme CSV output path.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Directory for multi-scheme outputs.")
    parser.add_argument("--max-tasks", type=int, default=None, help="Optional maximum number of teaching tasks to schedule.")
    parser.add_argument("--variant-count", type=int, default=1, help="Number of scheme variants to generate.")
    parser.add_argument("--random-seed", type=int, default=42, help="Base random seed for variant generation.")
    parser.add_argument("--policy", default=DEFAULT_POLICY, choices=list(POLICY_PROFILES.keys()), help="Generation policy profile.")
    parser.add_argument("--policy-params", default=None, help="JSON string of custom policy weights to override preset values.")
    parser.add_argument("--generation-config", default=None, help="JSON task generation config snapshot from allocation_task_generation_config.")
    parser.add_argument("--teacher-penalties", type=Path, required=True, help="Teacher penalty JSON prepared by Java orchestration.")
    parser.add_argument("--teaching-task-ids", default=None, help="Comma-separated teaching task IDs to schedule.")
    parser.add_argument("--start-week", type=int, default=None, help="Optional minimum week number.")
    parser.add_argument("--end-week", type=int, default=None, help="Optional maximum week number.")
    parser.add_argument("--exclude-weekends", action="store_true", help="Hard filter Saturday/Sunday time slots before model scoring.")
    parser.add_argument("--candidate-pool-size", type=int, default=DEFAULT_CANDIDATE_POOL_SIZE, help="Rule-filtered candidate pool size scored by the model per fragment.")
    parser.add_argument("--candidate-top-n", type=int, default=DEFAULT_CANDIDATE_TOP_N, help="Top-N scored candidates per fragment used by GA.")
    parser.add_argument("--population-size", type=int, default=DEFAULT_POPULATION_SIZE, help="GA population size.")
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS, help="GA generation count.")
    parser.add_argument("--elite-size", type=int, default=DEFAULT_ELITE_SIZE, help="GA elite size.")
    parser.add_argument("--tournament-size", type=int, default=DEFAULT_TOURNAMENT_SIZE, help="GA tournament selection size.")
    parser.add_argument("--mutation-rate", type=float, default=DEFAULT_MUTATION_RATE, help="GA gene mutation rate.")
    parser.add_argument("--predicted-score-weight", type=float, default=DEFAULT_PREDICTED_SCORE_WEIGHT)
    parser.add_argument("--rule-score-weight", type=float, default=DEFAULT_RULE_SCORE_WEIGHT)
    parser.add_argument("--hard-conflict-penalty", type=float, default=DEFAULT_HARD_CONFLICT_PENALTY)
    parser.add_argument("--teacher-profile-penalty-scale", type=float, default=DEFAULT_TEACHER_PROFILE_PENALTY_SCALE)
    parser.add_argument("--distribution-penalty-scale", type=float, default=DEFAULT_DISTRIBUTION_PENALTY_SCALE)
    parser.add_argument("--classroom-stickiness-weight", type=float, default=DEFAULT_CLASSROOM_STICKINESS_WEIGHT)
    parser.add_argument("--compact-bonus-weight", type=float, default=DEFAULT_COMPACT_BONUS_WEIGHT)
    parser.add_argument("--log-file", type=Path, default=None, help="Optional Python-side detailed log file path.")
    return parser.parse_args()


def run_ga_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    """Run the full GA scheme generation pipeline.

    Extracted from main() so both the CLI entry point and the FastAPI router
    can share the same logic. Returns a dict with output paths and summary.
    """
    configure_python_log(args.log_file)
    generation_config = load_generation_config(args.generation_config)
    allowed_weeks = parse_int_set(generation_config.get("allowedWeeks"))
    allowed_weekdays = parse_int_set(generation_config.get("allowedWeekdays"))
    allowed_periods = parse_int_set(generation_config.get("allowedPeriods"))
    booster, schema, scoring_mode = load_optional_lightgbm(args.model, args.schema)
    log_chain("排课方案生成链路启动", {
        "scoring_mode": scoring_mode,
        "model_path": str(args.model),
        "schema_path": str(args.schema),
        "variant_count": args.variant_count,
        "candidate_pool_size": args.candidate_pool_size,
        "candidate_top_n": args.candidate_top_n,
        "population_size": args.population_size,
        "generations": args.generations,
        "elite_size": args.elite_size,
        "tournament_size": args.tournament_size,
        "mutation_rate": args.mutation_rate,
        "policy": args.policy,
        "custom_policy_params": json.loads(args.policy_params) if args.policy_params else None,
        "teacher_penalties_path": str(args.teacher_penalties) if args.teacher_penalties else None,
        "teaching_task_ids": args.teaching_task_ids,
        "start_week": args.start_week,
        "end_week": args.end_week,
        "exclude_weekends": args.exclude_weekends,
        "allowed_weeks": sorted(allowed_weeks) if allowed_weeks else None,
        "allowed_weekdays": sorted(allowed_weekdays) if allowed_weekdays else None,
        "allowed_periods": sorted(allowed_periods) if allowed_periods else None,
        "generation_config": generation_config or None,
        "python_log_file": str(args.log_file) if args.log_file else None,
    })

    load_started_at = perf_counter()
    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)
    add_timing("load_data_time", load_started_at)

    tasks = filter_tasks(tasks, parse_teaching_task_ids(args.teaching_task_ids))
    before_config_time_slot_count = len(time_slots)
    time_slots = filter_time_slots(
        time_slots,
        args.start_week,
        args.end_week,
        allowed_weeks=allowed_weeks,
        allowed_weekdays=allowed_weekdays,
        allowed_periods=allowed_periods,
    )
    if allowed_weeks or allowed_weekdays or allowed_periods:
        log_chain("生成配置时间片硬约束生效", {
            "before_time_slot_count": before_config_time_slot_count,
            "after_time_slot_count": len(time_slots),
            "removed_time_slot_count": before_config_time_slot_count - len(time_slots),
            "allowed_weeks": sorted(allowed_weeks) if allowed_weeks else None,
            "allowed_weekdays": sorted(allowed_weekdays) if allowed_weekdays else None,
            "allowed_periods": sorted(allowed_periods) if allowed_periods else None,
        })
    if args.exclude_weekends:
        before_count = len(time_slots)
        time_slots = [slot for slot in time_slots if int(slot["day_of_week"]) < 6]
        log_chain("周末硬约束生效：已排除周六周日时间片", {
            "before_time_slot_count": before_count,
            "after_time_slot_count": len(time_slots),
            "removed_time_slot_count": before_count - len(time_slots),
        })
    if not tasks:
        raise ValueError("No teaching tasks available for scheme generation.")
    if not time_slots:
        raise ValueError("No time slots available for scheme generation.")
    log_chain("排课基础数据加载完成", {
        "teaching_task_count": len(tasks),
        "classroom_count": len(classrooms),
        "time_slot_count": len(time_slots),
        "teacher_profile_count": len(teacher_profiles),
        "tasks": [
            {
                "teaching_task_id": task.get("teaching_task_id"),
                "teacher_id": task.get("teacher_id"),
                "teacher_name": task.get("teacher_name"),
                "total_hours": task.get("total_hours"),
                "required_fragments": periods_needed(task),
                "class_group_ids": task.get("class_group_ids"),
                "bound_classroom_id": task.get("bound_classroom_id"),
                "required_room_type": effective_required_room_type(task),
            }
            for task in tasks
        ],
    })
    teacher_penalties = load_teacher_penalties(args.teacher_penalties)
    log_chain("教师画像惩罚由编排层提供", summarize_teacher_penalties(teacher_penalties))

    custom_params = policy_overrides_from_config(generation_config)
    if args.policy_params:
        custom_params.update(json.loads(args.policy_params))
    policy = load_policy(args.policy, custom_params)
    fitness_kwargs = {
        "predicted_score_weight": args.predicted_score_weight,
        "rule_score_weight": args.rule_score_weight,
        "hard_conflict_penalty": args.hard_conflict_penalty,
        "teacher_profile_penalty_scale": config_float(generation_config, "teacherProfilePenaltyScale", args.teacher_profile_penalty_scale),
        "distribution_penalty_scale": config_float(generation_config, "distributionPenaltyScale", args.distribution_penalty_scale),
        "classroom_stickiness_weight": config_float(generation_config, "classroomStickinessWeight", args.classroom_stickiness_weight),
        "compact_bonus_weight": config_float(generation_config, "compactBonusWeight", args.compact_bonus_weight),
    }
    log_chain("策略权重与 GA 适应度参数生效", {
        "policy": args.policy,
        "custom_params": custom_params,
        "effective_weights": policy,
        "fitness_weights": fitness_kwargs,
    })

    if args.variant_count <= 1:
        rows, _, metrics = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            teacher_profiles=teacher_penalties,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            rng=random.Random(args.random_seed),
            candidate_pool_size=args.candidate_pool_size,
            candidate_top_n=args.candidate_top_n,
            policy=policy,
            exclude_weekends=args.exclude_weekends,
            population_size=args.population_size,
            generations=args.generations,
            elite_size=args.elite_size,
            tournament_size=args.tournament_size,
            mutation_rate=args.mutation_rate,
            fitness_kwargs=fitness_kwargs,
        )
        write_scheme(rows, args.output)
        write_teacher_penalties(teacher_penalties, args.output.parent / TEACHER_PENALTIES_FILENAME)
        ga_summary_path = args.output.parent / "ga_summary.json"
        ga_summary_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        write_candidate_diagnostics(args.output.parent / "candidate_diagnostics.json")
        log_chain("单方案生成完成", {"output_path": str(args.output), **summarize_scheme(rows, tasks, args.max_tasks), **summarize_metrics(metrics), "timings_ms": dict(RUN_TIMINGS)})
        print_summary(rows, tasks, args.max_tasks)
        print(f"Output -> {args.output}")
        print(f"Teacher penalties -> {args.output.parent / TEACHER_PENALTIES_FILENAME}")
        return {
            "output_dir": str(args.output.parent),
            "scheme_count": 1,
            "schemes": [{"scheme_no": 1, "output_path": str(args.output), **summarize_scheme(rows, tasks, args.max_tasks), **summarize_metrics(metrics)}],
            "item_rows": [rows],  # one scheme's item rows
            "ga_summary_path": str(ga_summary_path),
            "candidate_diagnostics_path": str(args.output.parent / "candidate_diagnostics.json"),
            "timings_ms": dict(RUN_TIMINGS),
        }

    summary_rows: list[dict[str, Any]] = []
    all_item_rows: list[list[dict[str, Any]]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_teacher_penalties(teacher_penalties, args.output_dir / TEACHER_PENALTIES_FILENAME)
    for scheme_no in range(1, args.variant_count + 1):
        output_path = args.output_dir / f"scheme_{scheme_no:03d}.csv"
        rng = random.Random(args.random_seed + scheme_no)
        rows, _, metrics = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            teacher_profiles=teacher_penalties,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            rng=rng,
            candidate_pool_size=args.candidate_pool_size,
            candidate_top_n=args.candidate_top_n,
            policy=policy,
            exclude_weekends=args.exclude_weekends,
            population_size=args.population_size,
            generations=args.generations,
            elite_size=args.elite_size,
            tournament_size=args.tournament_size,
            mutation_rate=args.mutation_rate,
            fitness_kwargs=fitness_kwargs,
        )
        write_scheme(rows, output_path)
        summary = summarize_scheme(rows, tasks, args.max_tasks)
        summary_rows.append({"scheme_no": scheme_no, "output_path": str(output_path), **summary, **summarize_metrics(metrics)})
        all_item_rows.append(rows)

    summary_path = args.output_dir / "summary.csv"
    ga_summary_path = args.output_dir / "ga_summary.json"
    write_summary(summary_rows, summary_path)
    ga_summary_path.write_text(json.dumps({"schemes": summary_rows, "timings_ms": dict(RUN_TIMINGS)}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_candidate_diagnostics(args.output_dir / "candidate_diagnostics.json")
    log_chain("多方案生成完成", {"summary_rows": summary_rows, "summary_path": str(summary_path), "ga_summary_path": str(ga_summary_path), "candidate_diagnostics_path": str(args.output_dir / "candidate_diagnostics.json"), "timings_ms": dict(RUN_TIMINGS)})
    print(f"Generated {len(summary_rows)} scheme variants -> {args.output_dir}")
    print(f"Summary -> {summary_path}")
    return {
        "output_dir": str(args.output_dir),
        "scheme_count": len(summary_rows),
        "schemes": summary_rows,
        "item_rows": all_item_rows,
        "ga_summary_path": str(ga_summary_path),
        "candidate_diagnostics_path": str(args.output_dir / "candidate_diagnostics.json"),
        "timings_ms": dict(RUN_TIMINGS),
    }


def main() -> None:
    """CLI entry point — parse args then delegate to run_ga_pipeline."""
    args = parse_args()
    run_ga_pipeline(args)


if __name__ == "__main__":
    main()
