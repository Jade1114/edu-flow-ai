"""Generate model-driven scheduling scheme demos.

This script uses the trained LightGBM scoring model as the decision maker:

    teaching tasks -> candidate slots/rooms -> model scores -> selected fragments -> demo scheme CSV

It does not write to business tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
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

OUTPUT_COLUMNS = [
    "sequence",
    "teaching_task_id",
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
]

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
                    "is_early_period": is_early_period,
                    "is_late_period": is_late_period,
                    "teacher_occupied_at_slot": int(teacher_occupied),
                    "class_occupied_at_slot": int(class_occupied),
                    "room_occupied_at_slot": int(room_occupied),
                    "teacher_day_load": teacher_day_load,
                    "class_day_load": class_day_load,
                    "teacher_week_load": teacher_week_load,
                    "class_week_load": class_week_load,
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


def rank_candidates(
    *,
    booster: lgb.Booster,
    schema: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    features = build_features(candidates, schema)
    predictions = np.clip(booster.predict(features), 0.0, 1.0)
    for candidate, predicted_score in zip(candidates, predictions):
        candidate["predicted_score"] = float(predicted_score)

    return sorted(
        candidates,
        key=lambda row: (
            row["predicted_score"],
            -row["has_hard_conflict"],
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
) -> dict[str, Any] | None:
    ranked = rank_candidates(booster=booster, schema=schema, candidates=candidates)
    if not ranked:
        return None
    if strategy == "greedy":
        return ranked[0]
    if strategy == "top-k-random":
        legal_ranked = [candidate for candidate in ranked if int(candidate["has_hard_conflict"]) == 0]
        pool = legal_ranked if legal_ranked else ranked
        return rng.choice(pool[: max(1, min(top_k, len(pool)))])
    raise ValueError(f"Unsupported selection strategy: {strategy}")


def generate_scheme(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    booster: lgb.Booster,
    schema: dict[str, Any],
    max_tasks: int | None,
    strategy: str,
    top_k: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[PseudoAssignment]]:
    scheme_rows: list[dict[str, Any]] = []
    selected_assignments: list[PseudoAssignment] = []
    sequence = 1

    scoped_tasks = tasks[:max_tasks] if max_tasks is not None else tasks
    for task in scoped_tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        required_fragments = periods_needed(task)

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
            )
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
            scheme_rows.append(
                {
                    "sequence": sequence,
                    "teaching_task_id": task_id,
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}. Run train_lightgbm.py first.")
    schema = load_schema(args.schema)
    booster = lgb.Booster(model_file=str(args.model))

    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)

    if args.variant_count <= 1:
        rows, _ = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            strategy=args.strategy,
            top_k=args.top_k,
            rng=random.Random(args.random_seed),
        )
        write_scheme(rows, args.output)
        print_summary(rows, tasks, args.max_tasks)
        print(f"Output -> {args.output}")
        return

    summary_rows: list[dict[str, Any]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for scheme_no in range(1, args.variant_count + 1):
        output_path = args.output_dir / f"scheme_{scheme_no:03d}.csv"
        rng = random.Random(args.random_seed + scheme_no)
        rows, _ = generate_scheme(
            tasks=tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            booster=booster,
            schema=schema,
            max_tasks=args.max_tasks,
            strategy=args.strategy,
            top_k=args.top_k,
            rng=rng,
        )
        write_scheme(rows, output_path)
        summary = summarize_scheme(rows, tasks, args.max_tasks)
        summary_rows.append({"scheme_no": scheme_no, "output_path": str(output_path), **summary})

    write_summary(summary_rows, SUMMARY_PATH)
    print(f"Generated {len(summary_rows)} scheme variants -> {args.output_dir}")
    print(f"Summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
