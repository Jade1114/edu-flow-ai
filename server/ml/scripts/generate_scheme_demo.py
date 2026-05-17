"""Generate model-driven scheduling scheme demos.

This script uses the trained LightGBM scoring model as the decision maker:

    teaching tasks -> candidate slots/rooms -> model scores -> selected fragments -> demo scheme CSV

It does not write to business tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import lightgbm as lgb
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
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"
OUTPUT_PATH = ROOT_DIR / "data" / "generated_scheme_demo.csv"
OUTPUT_DIR = ROOT_DIR / "data" / "generated_schemes"
SUMMARY_PATH = OUTPUT_DIR / "summary.csv"
PROMPT_DIR = ROOT_DIR / "prompts"

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

SUMMARY_COLUMNS = [
    "scheme_no",
    "output_path",
    "tasks",
    "expected_fragments",
    "generated_fragments",
    "hard_conflict_fragments",
    "avg_predicted_score",
    "avg_rule_score",
]

WEEKDAY_LOAD_PENALTY = 0.004
ROOM_DAY_LOAD_PENALTY = 0.012
ROOM_WEEK_LOAD_PENALTY = 0.003
TASK_DAY_LOAD_PENALTY = 0.018
RANDOM_JITTER = 0.002
DEFAULT_CANDIDATE_POOL_SIZE = 500

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


def log_chain(message: str, payload: Any | None = None) -> None:
    if payload is None:
        print(f"{LOG_PREFIX} {message}", flush=True)
        return
    print(f"{LOG_PREFIX} {message}: {json.dumps(payload, ensure_ascii=False, default=str)}", flush=True)


def load_prompt(file_name: str) -> str:
    return (PROMPT_DIR / file_name).read_text(encoding="utf-8").strip()


def load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}. Run train_lightgbm.py first.")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def build_candidate_rows(
    *,
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    selected_assignments: list[PseudoAssignment],
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
    rows: list[dict[str, Any]] = []

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

        for room in classrooms:
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
    booster: lgb.Booster,
    schema: dict[str, Any],
    candidates: list[dict[str, Any]],
    rng: random.Random,
    policy: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    features = build_features(candidates, schema)
    predictions = np.clip(booster.predict(features), 0.0, 1.0)
    for candidate, predicted_score in zip(candidates, predictions):
        candidate["predicted_score"] = float(predicted_score)
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


def choose_candidate(
    *,
    booster: lgb.Booster,
    schema: dict[str, Any],
    candidates: list[dict[str, Any]],
    strategy: str,
    top_k: int,
    rng: random.Random,
    candidate_pool_size: int,
    policy: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> dict[str, Any] | None:
    candidates = shortlist_candidates(candidates, candidate_pool_size, rng, policy)
    ranked = rank_candidates(
        booster=booster, schema=schema, candidates=candidates, rng=rng, policy=policy,
        task_classroom_id=task_classroom_id, teacher_id=teacher_id, teacher_profiles=teacher_profiles,
    )
    if not ranked:
        return None
    penalty_stats = summarize_teacher_profile_penalty_candidates(ranked)
    if strategy == "greedy":
        selected = ranked[0]
        selected["teacher_profile_candidate_stats"] = penalty_stats
        return selected
    if strategy == "top-k-random":
        legal_ranked = [candidate for candidate in ranked if int(candidate["has_hard_conflict"]) == 0]
        pool = legal_ranked if legal_ranked else ranked
        selected = rng.choice(pool[: max(1, min(top_k, len(pool)))])
        selected["teacher_profile_candidate_stats"] = penalty_stats
        return selected
    raise ValueError(f"Unsupported selection strategy: {strategy}")


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
) -> list[dict[str, Any]]:
    return [
        slot
        for slot in time_slots
        if (start_week is None or int(slot["week_number"]) >= start_week)
        and (end_week is None or int(slot["week_number"]) <= end_week)
    ]


def parse_teaching_task_ids(raw_value: str | None) -> set[int] | None:
    if not raw_value:
        return None
    return {int(value.strip()) for value in raw_value.split(",") if value.strip()}


def build_teacher_penalty_query(tasks: list[dict[str, Any]]) -> str:
    parts = []
    for task in tasks:
        parts.append(
            "教学任务{task_id}-教师{teacher_id}-课程类型{course_type}-班级{class_groups}".format(
                task_id=task.get("teaching_task_id"),
                teacher_id=task.get("teacher_id"),
                course_type=task.get("course_type") or "未知",
                class_groups=task.get("class_group_ids") or "未知",
            )
        )
    return "；".join(parts)


def post_json(url: str, body: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def resolve_teacher_penalties(tasks: list[dict[str, Any]], teacher_profiles: dict[int, dict[str, object]]) -> dict[int, dict[str, Any]]:
    fallback = fallback_teacher_penalties(teacher_profiles)
    embedding_api_key = os.getenv("OPENAI_API_KEY")
    embedding_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    chat_api_key = os.getenv("OPENAI_CHAT_API_KEY")
    chat_base_url = os.getenv("OPENAI_CHAT_BASE_URL", "").rstrip("/")
    chat_model = os.getenv("OPENAI_CHAT_MODEL", "deepseek-v4-pro")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "teacher_profiles")

    log_chain("教师画像惩罚解析开始", {
        "task_count": len(tasks),
        "fallback_profile_count": len(fallback),
        "rag_enabled": bool(embedding_api_key and chat_api_key and chat_base_url),
        "embedding_model": embedding_model,
        "chat_model": chat_model,
        "qdrant_collection": qdrant_collection,
    })
    if not (embedding_api_key and chat_api_key and chat_base_url):
        log_chain("教师画像惩罚使用 MySQL fallback（未配置完整 Embedding/Chat 环境变量）", summarize_teacher_penalties(fallback))
        return fallback

    try:
        query = build_teacher_penalty_query(tasks)
        log_chain("LLM/RAG 教师画像检索 Query", {"query": query})
        embedding_response = post_json(
            f"{embedding_base_url}/embeddings",
            {"model": embedding_model, "input": query},
            {"Authorization": f"Bearer {embedding_api_key}"},
        )
        vector = embedding_response["data"][0]["embedding"]
        log_chain("Embedding 完成", {"vector_size": len(vector)})
        qdrant_headers = {"api-key": qdrant_api_key} if qdrant_api_key else None
        qdrant_limit = min(max(len({int(task["teacher_id"]) for task in tasks}) + 3, 5), 20)
        log_chain("Qdrant 检索教师画像", {"url": qdrant_url, "collection": qdrant_collection, "top_n": qdrant_limit})
        search_response = post_json(
            f"{qdrant_url}/collections/{qdrant_collection}/points/search",
            {
                "vector": vector,
                "limit": qdrant_limit,
                "with_payload": True,
                "with_vector": False,
                "filter": {"must": [{"key": "status", "match": {"value": "ACTIVE"}}]},
            },
            qdrant_headers,
        )
        profiles = [item.get("payload", {}) for item in search_response.get("result", [])]
        log_chain("Qdrant 返回教师画像", {
            "profile_count": len(profiles),
            "teachers": [
                {
                    "teacher_id": profile.get("teacherId"),
                    "teacher_name": profile.get("teacherName"),
                    "department": profile.get("department"),
                    "has_special_note": bool(profile.get("specialNote")),
                }
                for profile in profiles
            ],
        })
        payload_json = json.dumps(
            {"teaching_tasks": tasks, "teacher_profiles": profiles},
            ensure_ascii=False,
            default=str,
        )
        system_prompt = load_prompt("teacher-penalty-system.md")
        user_prompt = load_prompt("teacher-penalty-user-template.md").replace("{payload_json}", payload_json)
        chat_response = post_json(
            f"{chat_base_url}/chat/completions",
            {
                "model": chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            {"Authorization": f"Bearer {chat_api_key}"},
            timeout=600,
        )
        content = chat_response["choices"][0]["message"]["content"]
        log_chain("LLM 教师画像结构化原始输出", json.loads(content))
        penalties = normalize_teacher_penalties(json.loads(content))
        resolved = penalties or fallback
        log_chain("教师画像惩罚最终结构", summarize_teacher_penalties(resolved))
        return resolved
    except (KeyError, ValueError, urllib.error.URLError, TimeoutError) as exc:
        log_chain("教师画像惩罚 RAG 失败，回退 MySQL 解析", {"error": str(exc), "fallback": summarize_teacher_penalties(fallback)})
        return fallback


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


def generate_scheme(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    booster: lgb.Booster,
    schema: dict[str, Any],
    max_tasks: int | None,
    strategy: str,
    top_k: int,
    rng: random.Random,
    candidate_pool_size: int,
    policy: dict[str, float],
) -> tuple[list[dict[str, Any]], list[PseudoAssignment]]:
    scheme_rows: list[dict[str, Any]] = []
    selected_assignments: list[PseudoAssignment] = []
    task_classroom_map: dict[int, int] = {}  # task_id -> first chosen classroom_id
    sequence = 1

    scoped_tasks = tasks[:max_tasks] if max_tasks is not None else tasks
    for task in scoped_tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        required_fragments = periods_needed(task)
        task_classroom = task_classroom_map.get(task_id)

        for fragment_index in range(1, required_fragments + 1):
            candidates = build_candidate_rows(
                task=task,
                classrooms=classrooms,
                time_slots=time_slots,
                selected_assignments=selected_assignments,
            )
            best = choose_candidate(
                booster=booster,
                schema=schema,
                candidates=candidates,
                strategy=strategy,
                top_k=top_k,
                rng=rng,
                candidate_pool_size=candidate_pool_size,
                policy=policy,
                task_classroom_id=task_classroom,
                teacher_id=teacher_id,
                teacher_profiles=teacher_profiles,
            )
            if best is None:
                log_chain("模型未选出可用候选", {
                    "teaching_task_id": task_id,
                    "teacher_id": teacher_id,
                    "fragment_index": fragment_index,
                    "candidate_count": len(candidates),
                })
                continue
            log_selected_candidate(task, fragment_index, best, len(candidates))
            # Track first classroom for this task
            chosen_room = int(best["candidate_classroom_id"])
            if task_id not in task_classroom_map:
                task_classroom_map[task_id] = chosen_room
            if best is None:
                continue

            assignment = PseudoAssignment(
                task_id=task_id,
                teacher_id=teacher_id,
                class_group_ids=class_group_ids,
                classroom_id=int(best["candidate_classroom_id"]),
                time_slot_id=int(best["candidate_time_slot_id"]),
                week_number=int(best["week_number"]),
                day_of_week=int(best["day_of_week"]),
                period_index=int(best["period_index"]),
            )
            selected_assignments.append(assignment)
            penalty_breakdown = best.get("teacher_profile_penalty_breakdown") or []
            scheme_rows.append(
                {
                    "sequence": sequence,
                    "teaching_task_id": task_id,
                    "teacher_id": teacher_id,
                    "teacher_name": task.get("teacher_name") or "",
                    "fragment_index": fragment_index,
                    "classroom_id": assignment.classroom_id,
                    "time_slot_id": assignment.time_slot_id,
                    "week_number": assignment.week_number,
                    "day_of_week": assignment.day_of_week,
                    "period_index": assignment.period_index,
                    "predicted_score": round(float(best["predicted_score"]), 4),
                    "rule_score": best["rule_score"],
                    "has_hard_conflict": best["has_hard_conflict"],
                    "reject_reason": best["reject_reason"],
                    "teacher_profile_penalty": best.get("teacher_profile_penalty") or 0.0,
                    "teacher_profile_penalty_explanation": format_teacher_profile_penalty_explanation(best),
                    "teacher_profile_penalty_breakdown": json.dumps(penalty_breakdown, ensure_ascii=False),
                }
            )
            sequence += 1
    return scheme_rows, selected_assignments


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


def print_summary(rows: list[dict[str, Any]], tasks: list[dict[str, Any]], max_tasks: int | None) -> None:
    summary = summarize_scheme(rows, tasks, max_tasks)
    print("Generated model-driven scheduling demo")
    print(f"Tasks: {summary['tasks']}")
    print(f"Expected fragments: {summary['expected_fragments']}")
    print(f"Generated fragments: {summary['generated_fragments']}")
    print(f"Hard-conflict fragments: {summary['hard_conflict_fragments']}")
    print(f"Average predicted score: {summary['avg_predicted_score']:.4f}")
    print(f"Average rule score: {summary['avg_rule_score']:.4f}")


def write_summary(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model-driven scheduling scheme demos.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Trained LightGBM model path.")
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH, help="Feature schema JSON path.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Single generated scheme CSV output path.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Directory for multi-scheme outputs.")
    parser.add_argument("--max-tasks", type=int, default=None, help="Optional maximum number of teaching tasks to schedule.")
    parser.add_argument("--variant-count", type=int, default=1, help="Number of scheme variants to generate.")
    parser.add_argument("--strategy", choices=["greedy", "top-k-random"], default="greedy", help="Candidate selection strategy.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K candidate pool size for top-k-random strategy.")
    parser.add_argument("--random-seed", type=int, default=42, help="Base random seed for variant generation.")
    parser.add_argument("--policy", default=DEFAULT_POLICY, choices=list(POLICY_PROFILES.keys()), help="Generation policy profile.")
    parser.add_argument("--policy-params", default=None, help="JSON string of custom policy weights to override preset values.")
    parser.add_argument("--teacher-penalties", type=Path, default=None, help="Teacher penalty JSON prepared by Java orchestration.")
    parser.add_argument("--teaching-task-ids", default=None, help="Comma-separated teaching task IDs to schedule.")
    parser.add_argument("--start-week", type=int, default=None, help="Optional minimum week number.")
    parser.add_argument("--end-week", type=int, default=None, help="Optional maximum week number.")
    parser.add_argument(
        "--candidate-pool-size",
        type=int,
        default=DEFAULT_CANDIDATE_POOL_SIZE,
        help="Rule-filtered candidate pool size scored by the model per fragment. Use 0 for full scoring.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}. Run train_lightgbm.py first.")
    schema = load_schema(args.schema)
    booster = lgb.Booster(model_file=str(args.model))
    log_chain("排课方案生成链路启动", {
        "model_path": str(args.model),
        "schema_path": str(args.schema),
        "variant_count": args.variant_count,
        "strategy": args.strategy,
        "top_k": args.top_k,
        "candidate_pool_size": args.candidate_pool_size,
        "policy": args.policy,
        "custom_policy_params": json.loads(args.policy_params) if args.policy_params else None,
        "teacher_penalties_path": str(args.teacher_penalties) if args.teacher_penalties else None,
        "teaching_task_ids": args.teaching_task_ids,
        "start_week": args.start_week,
        "end_week": args.end_week,
    })

    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)

    tasks = filter_tasks(tasks, parse_teaching_task_ids(args.teaching_task_ids))
    time_slots = filter_time_slots(time_slots, args.start_week, args.end_week)
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
    teacher_penalties = load_teacher_penalties(args.teacher_penalties) if args.teacher_penalties else fallback_teacher_penalties(teacher_profiles)
    log_chain("教师画像惩罚由编排层提供" if args.teacher_penalties else "教师画像惩罚使用 Python fallback", summarize_teacher_penalties(teacher_penalties))

    custom_params = None
    if args.policy_params:
        custom_params = json.loads(args.policy_params)
    policy = load_policy(args.policy, custom_params)
    log_chain("策略权重生效", {
        "policy": args.policy,
        "custom_params": custom_params,
        "effective_weights": policy,
        "candidate_score_formula": "selection_score = predicted_score + rule_score*0.02 - distribution_penalty + compact_bonus + stickiness_bonus - teacher_profile_penalty + random_jitter",
        "distribution_penalty_formula": "scheme_day_load*weekday_load_penalty + room_day_load*room_day_load_penalty + room_week_load*room_week_load_penalty + task_day_load*task_day_load_penalty + weekend + early + late",
    })

    if args.variant_count <= 1:
        rows, _ = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            teacher_profiles=teacher_penalties,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            strategy=args.strategy,
            top_k=args.top_k,
            rng=random.Random(args.random_seed),
            candidate_pool_size=args.candidate_pool_size,
            policy=policy,
        )
        write_scheme(rows, args.output)
        write_teacher_penalties(teacher_penalties, args.output.parent / TEACHER_PENALTIES_FILENAME)
        log_chain("单方案生成完成", {"output_path": str(args.output), **summarize_scheme(rows, tasks, args.max_tasks)})
        print_summary(rows, tasks, args.max_tasks)
        print(f"Output -> {args.output}")
        print(f"Teacher penalties -> {args.output.parent / TEACHER_PENALTIES_FILENAME}")
        return

    summary_rows: list[dict[str, Any]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_teacher_penalties(teacher_penalties, args.output_dir / TEACHER_PENALTIES_FILENAME)
    for scheme_no in range(1, args.variant_count + 1):
        output_path = args.output_dir / f"scheme_{scheme_no:03d}.csv"
        rng = random.Random(args.random_seed + scheme_no)
        rows, _ = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            teacher_profiles=teacher_penalties,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            strategy=args.strategy,
            top_k=args.top_k,
            rng=rng,
            candidate_pool_size=args.candidate_pool_size,
            policy=policy,
        )
        write_scheme(rows, output_path)
        summary = summarize_scheme(rows, tasks, args.max_tasks)
        summary_rows.append({"scheme_no": scheme_no, "output_path": str(output_path), **summary})

    write_summary(summary_rows, SUMMARY_PATH)
    log_chain("多方案生成完成", {"summary_rows": summary_rows, "summary_path": str(SUMMARY_PATH)})
    print(f"Generated {len(summary_rows)} scheme variants -> {args.output_dir}")
    print(f"Summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
