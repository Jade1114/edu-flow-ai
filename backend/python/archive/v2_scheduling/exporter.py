"""Write solved candidate-index chromosomes to Java-compatible files."""

from __future__ import annotations

import json
from datetime import datetime as dt
from pathlib import Path
from typing import Any

from python.scheduling_v2.models import ScheduleContext, SolvedScheme, TaskCandidate


def write_output(
    context: ScheduleContext,
    schemes: list[SolvedScheme],
    pools: list[list[TaskCandidate]],
    candidate_pool_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    output_dir = Path(__file__).resolve().parents[1] / "data" / "generated" / f"task_{context.task_id}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    scheme_rows = [_scheme_to_json(scheme) for scheme in schemes]
    (output_dir / "schemes.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in scheme_rows),
        encoding="utf-8",
    )

    summary = {
        "architecture": "candidate_pool_ga",
        "task_id": context.task_id,
        "scheme_count": len(schemes),
        "task_count": len(context.tasks),
        "room_ranker": {
            "enabled": True,
            "model_path": "ml/models/v2/room_ranker.txt",
            "score_field": "room_rank_score",
            "input": "teaching_task + classrooms",
            "output": "ranked classrooms",
        },
        "candidate_pool": {
            "pool_count": len(pools),
            "min_candidates": min(len(pool) for pool in pools) if pools else 0,
            "max_candidates": max(len(pool) for pool in pools) if pools else 0,
            "total_candidates": sum(len(pool) for pool in pools),
            **(candidate_pool_stats or {}),
        },
        "schemes": [
            {
                "scheme_index": scheme.scheme_index,
                "hard_conflicts": scheme.fitness.hard_conflicts,
                "quality_score": scheme.fitness.quality_score,
                "assignment_count": scheme.fitness.assignment_count,
                "conflict_summary": scheme.fitness.conflict_summary,
                "chromosome": list(scheme.chromosome),
            }
            for scheme in schemes
        ],
    }
    (output_dir / "ga_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    return {
        "output_dir": str(output_dir),
        "scheme_count": len(schemes),
        "timings_ms": {
            "candidate_pool": (candidate_pool_stats or {}).get("candidate_pool_elapsed_ms", 0.0),
        },
    }


def _scheme_to_json(scheme: SolvedScheme) -> dict[str, Any]:
    return {
        "items": [
            {
                "teaching_task_id": assignment.teaching_task_id,
                "teacher_id": assignment.teacher_id,
                "classroom_id": assignment.classroom_id,
                "time_slot_id": assignment.time_slot_id,
                "week_number": assignment.week_number,
                "day_of_week": assignment.day_of_week,
                "period_index": assignment.period_index,
                "predicted_score": assignment.room_rank_score,
                "room_rank_score": assignment.room_rank_score,
                "teacher_profile_penalty": assignment.teacher_profile_penalty,
                "teacher_profile_penalty_explanation": assignment.teacher_profile_penalty_explanation,
            }
            for assignment in scheme.assignments
        ]
    }
