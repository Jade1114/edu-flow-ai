"""Constants and default paths for GA scheduling generation.

Note: CANDIDATE_DIAGNOSTICS is a mutable global dict shared across modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]  # ml/scheduling/infra/ → ml/
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # → 项目根目录
PROJECT_LOG_DIR = PROJECT_ROOT / "logs" / "python"
BASE_MODEL_PATH = ROOT_DIR / "models" / "base" / "schedule_ranker_v1.txt"
BASE_FEATURE_SCHEMA_PATH = ROOT_DIR / "models" / "base" / "feature_schema.json"
FEEDBACK_MODEL_PATH = ROOT_DIR / "models" / "feedback" / "current" / "schedule_ranker.txt"
FEEDBACK_FEATURE_SCHEMA_PATH = ROOT_DIR / "models" / "feedback" / "current" / "feature_schema.json"
MODEL_PATH = FEEDBACK_MODEL_PATH if FEEDBACK_MODEL_PATH.exists() else BASE_MODEL_PATH
FEATURE_SCHEMA_PATH = FEEDBACK_FEATURE_SCHEMA_PATH if FEEDBACK_FEATURE_SCHEMA_PATH.exists() else BASE_FEATURE_SCHEMA_PATH
OUTPUT_DIR = ROOT_DIR / "data" / "generated"

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

SUMMARY_COLUMNS = [
    "scheme_no",
    "output_path",
    "tasks",
    "expected_fragments",
    "generated_fragments",
    "hard_conflict_fragments",
    "avg_predicted_score",
    "avg_rule_score",
    "quality_score",
    "penalty_count",
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

WEEKLY_TEMPLATE_SLOTS = int(os.environ.get("ML_GA_WEEKLY_SLOTS", "2"))

# ── Shared mutable state ────────────────────────────────────────
LOG_PREFIX = "[SCHEDULE-CHAIN]"

CANDIDATE_DIAGNOSTICS: dict[int, dict[str, Any]] = {}
