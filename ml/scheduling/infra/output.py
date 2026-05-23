"""Output writers and summary helpers for generated scheduling schemes."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from ml.scheduling.domain.features import periods_needed


def write_scheme(rows: list[dict[str, Any]], output_path: Path, fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_schemes_json(output_dir: Path, schemes: list[dict[str, Any]]) -> None:
    """Write all generated schemes as a single JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "schemes.json"
    output_path.write_text(
        json.dumps(schemes, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


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


def print_summary(
    rows: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    max_tasks: int | None,
    logger: logging.Logger | None = None,
) -> None:
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
    for line in lines:
        print(line)
        if logger is not None:
            logger.info("SCHEDULE %s", line)


def write_summary(rows: list[dict[str, Any]], output_path: Path, fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_candidate_diagnostics(
    output_path: Path,
    diagnostics_by_task: dict[int, dict[str, Any]],
    timings_ms: dict[str, float],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = sorted(diagnostics_by_task.values(), key=lambda item: item["task_id"])
    payload = {
        "summary": {
            "task_count": len(diagnostics),
            "infeasible_task_count": sum(1 for item in diagnostics if not item.get("has_any_feasible_candidate")),
            "missing_fragment_count": sum(int(item.get("missing_fragment_count") or 0) for item in diagnostics),
            "skipped_infeasible_task_ids": [
                item["task_id"] for item in diagnostics if not item.get("has_any_feasible_candidate")
            ],
            "timings_ms": {key: round(value, 3) for key, value in timings_ms.items()},
        },
        "tasks": diagnostics,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
