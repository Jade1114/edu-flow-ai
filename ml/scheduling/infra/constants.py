"""Constants and default paths for GA scheduling generation.

Note: CANDIDATE_DIAGNOSTICS is a mutable global dict shared across modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT_DIR.parent
PROJECT_LOG_DIR = PROJECT_ROOT / "logs" / "python"
BASE_MODEL_PATH = ROOT_DIR / "models" / "base" / "schedule_ranker_v1.txt"
BASE_FEATURE_SCHEMA_PATH = ROOT_DIR / "models" / "base" / "feature_schema.json"
FEEDBACK_MODEL_PATH = ROOT_DIR / "models" / "feedback" / "current" / "schedule_ranker.txt"
FEEDBACK_FEATURE_SCHEMA_PATH = ROOT_DIR / "models" / "feedback" / "current" / "feature_schema.json"
MODEL_PATH = FEEDBACK_MODEL_PATH if FEEDBACK_MODEL_PATH.exists() else BASE_MODEL_PATH
FEATURE_SCHEMA_PATH = FEEDBACK_FEATURE_SCHEMA_PATH if FEEDBACK_FEATURE_SCHEMA_PATH.exists() else BASE_FEATURE_SCHEMA_PATH
OUTPUT_DIR = ROOT_DIR / "data" / "generated"
OUTPUT_PATH = OUTPUT_DIR / "generated_scheme_ga.csv"
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

TEACHER_PENALTIES_FILENAME = "teacher_penalties.json"
LOG_PREFIX = "[SCHEDULE-CHAIN]"

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
TOTAL_WEEKS = 18
WEEKLY_TEMPLATE_SLOTS = int(os.environ.get("ML_GA_WEEKLY_SLOTS", "2"))

# ── Shared mutable state ────────────────────────────────────────
LOG_PREFIX = "[SCHEDULE-CHAIN]"

CANDIDATE_DIAGNOSTICS: dict[int, dict[str, Any]] = {}

DEFAULT_RULE_WEIGHTS = {
    "weekday_load_penalty": WEEKDAY_LOAD_PENALTY,
    "room_day_load_penalty": ROOM_DAY_LOAD_PENALTY,
    "room_week_load_penalty": ROOM_WEEK_LOAD_PENALTY,
    "task_day_load_penalty": TASK_DAY_LOAD_PENALTY,
    "early_period_penalty": 0.0,
    "late_period_penalty": 0.0,
    "compact_bonus_weight": DEFAULT_COMPACT_BONUS_WEIGHT,
    "random_jitter": RANDOM_JITTER,
    "classroom_stickiness_bonus": 0.0,
    "weekend_penalty": 0.0,
}
