"""Run a local prediction demo with the trained schedule scoring model.

Inputs:
    ../models/schedule_ranker_v1.txt
    ../data/feature_schema.json
    ../data/training_samples.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"
DATA_PATH = ROOT_DIR / "data" / "training_samples.csv"

DISPLAY_COLUMNS = [
    "teaching_task_id",
    "candidate_classroom_id",
    "candidate_time_slot_id",
    "score",
    "predicted_score",
    "reject_reason",
]


def load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}. Run train_lightgbm.py first.")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_demo_rows(data_path: Path, limit: int) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(f"Training samples not found: {data_path}. Run generate_training_samples.py first.")
    dataset = pd.read_csv(data_path)
    if dataset.empty:
        raise ValueError(f"Training samples are empty: {data_path}")

    if "score" not in dataset.columns:
        raise ValueError("Column `score` is required for demo comparison")

    # Pick a small, readable mix: best samples, rejected samples, and deterministic middle rows.
    accepted = dataset[dataset["score"] > 0].head(max(1, limit // 3))
    rejected = dataset[dataset["score"] == 0].head(max(1, limit // 3))
    middle = dataset.iloc[:: max(1, len(dataset) // max(1, limit))].head(limit)
    rows = pd.concat([accepted, rejected, middle], ignore_index=True).drop_duplicates("sample_id")
    return rows.head(limit).copy()


def build_features(rows: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    feature_columns = schema["feature_columns"]
    categorical_columns = schema["categorical_columns"]

    missing_columns = [column for column in feature_columns if column not in rows.columns]
    if missing_columns:
        raise ValueError(f"Demo rows are missing required feature columns: {missing_columns}")

    features = rows[feature_columns].copy()
    for column in categorical_columns:
        features[column] = features[column].fillna("UNKNOWN").astype("category")

    numeric_columns = [column for column in feature_columns if column not in categorical_columns]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local prediction demo with the trained schedule scorer.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Trained LightGBM model path.")
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH, help="Feature schema JSON path.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Training samples CSV path for demo rows.")
    parser.add_argument("--limit", type=int, default=10, help="Number of demo rows to score.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}. Run train_lightgbm.py first.")

    schema = load_schema(args.schema)
    rows = load_demo_rows(args.data, args.limit)
    features = build_features(rows, schema)

    booster = lgb.Booster(model_file=str(args.model))
    predictions = np.clip(booster.predict(features), 0.0, 1.0)
    rows["predicted_score"] = predictions.round(4)

    available_display_columns = [column for column in DISPLAY_COLUMNS if column in rows.columns]
    print(rows[available_display_columns].to_string(index=False))

    mean_abs_error = float(np.mean(np.abs(rows["score"].to_numpy() - predictions)))
    print(f"\nDemo rows: {len(rows)}")
    print(f"Mean absolute error on demo rows: {mean_abs_error:.6f}")


if __name__ == "__main__":
    main()
