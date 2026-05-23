"""Default paths and feature settings for LightGBM training."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "base" / "samples.csv"
MODEL_PATH = ROOT_DIR / "models" / "base" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "models" / "base" / "feature_schema.json"
TARGET_COLUMN = "score"
EXCLUDED_COLUMNS = {
    "sample_id",
    "teaching_task_id",
    "candidate_classroom_id",
    "candidate_time_slot_id",
    "reject_reason",
    "sample_weight",
    TARGET_COLUMN,
}
CATEGORICAL_COLUMNS = [
    "course_type",
    "required_room_type",
    "teacher_department",
    "teacher_title",
    "room_type",
    "room_building",
]
MODEL_PARAMS = {
    "objective": "regression",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 20,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "random_state": 42,
    "n_jobs": -1,
}
TRAIN_TEST_SPLIT = {
    "test_size": 0.2,
    "random_state": 42,
}
