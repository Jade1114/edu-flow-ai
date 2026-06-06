"""Training endpoint — trigger LightGBM training from feedback data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from python.api.schemas import TrainRequest, TrainResponse
from python.scheduling.model_training import run_training_pipeline
from python.scheduling.training_samples import build_samples

router = APIRouter(tags=["training"])


def _count_csv(path: Path) -> tuple[int, int, int]:
    """Count total rows, positive labels, and negative labels in a CSV."""
    total = 0
    pos = 0
    neg = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            label = row.get("score", "").strip()
            try:
                v = float(label)
                if v > 0:
                    pos += 1
                elif v < 0:
                    neg += 1
            except (ValueError, TypeError):
                pass
    return total, pos, neg


def _count_csv_lines(path: Path) -> int:
    """Quick line count (excluding header) for a CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return sum(1 for _ in reader) - 1  # subtract header


@router.post("/train", response_model=TrainResponse)
async def train(req: TrainRequest, _request: Request) -> TrainResponse:
    try:
        sample_path: Path | None = None

        # ── Step 1: Build training samples from feedback export ──────
        if req.feedback_export_path:
            feedback_path = Path(req.feedback_export_path)
            if not feedback_path.exists():
                return TrainResponse(success=False, error=f"Feedback export not found: {feedback_path}")

            export_data = json.loads(feedback_path.read_text(encoding="utf-8"))
            samples = build_samples(export_data)

            sample_path = Path(req.output_sample_path) if req.output_sample_path else feedback_path.with_suffix(".samples.csv")
            sample_path.parent.mkdir(parents=True, exist_ok=True)

            fieldnames = [
                "sample_id", "teaching_task_id", "candidate_classroom_id",
                "candidate_time_slot_id", "score", "sample_weight",
                "reject_reason", "course_type", "required_room_type",
                "teacher_department", "teacher_title", "teacher_max_weekly_hours",
                "room_type", "room_building", "room_capacity",
                "student_count", "day_of_week", "period_index",
                "week_number", "teacher_availability", "classroom_availability",
                "has_hard_conflict", "predicted_score", "rule_score",
                "teacher_profile_penalty",
            ]
            with open(sample_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(samples)

            sample_count, pos_count, neg_count = _count_csv(sample_path)
        else:
            sample_count = None
            pos_count = None
            neg_count = None

        # ── Step 2: Train LightGBM ──────────────────────────────────
        result = run_training_pipeline(
            training_data_dir=str(sample_path.parent) if sample_path else req.training_data_dir or None,
            output_model_path=req.output_model_path or None,
            output_schema_path=req.output_schema_path or None,
            **req.training_params,
        )

        return TrainResponse(
            success=True,
            model_path=result.get("model_path"),
            schema_path=result.get("schema_path"),
            sample_path=str(sample_path) if sample_path else None,
            sample_count=sample_count,
            positive_count=pos_count,
            negative_count=neg_count,
            metrics=result.get("metrics"),
        )

    except Exception as exc:
        return TrainResponse(success=False, error=str(exc))
