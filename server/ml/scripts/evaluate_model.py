"""Evaluate the trained LightGBM schedule scoring model.

Inputs:
    ../models/schedule_ranker_v1.txt
    ../data/feature_schema.json
    ../data/training_samples.csv

This script focuses on distribution-level checks, not only aggregate metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "base" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "training" / "feature_schema.json"
DATA_PATH = ROOT_DIR / "data" / "training" / "samples.csv"
TARGET_COLUMN = "score"

GROUP_COLUMNS = [
    "has_hard_conflict",
    "has_teacher_conflict",
    "has_class_conflict",
    "has_room_conflict",
    "is_capacity_enough",
    "is_room_type_match",
    "is_early_period",
    "is_late_period",
]


def load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}. Run train_lightgbm.py first.")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_dataset(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(f"Training samples not found: {data_path}. Run generate_training_samples.py first.")
    dataset = pd.read_csv(data_path)
    if dataset.empty:
        raise ValueError(f"Training samples are empty: {data_path}")
    if TARGET_COLUMN not in dataset.columns:
        raise ValueError(f"Target column `{TARGET_COLUMN}` is missing from {data_path}")
    return dataset


def build_features(dataset: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    feature_columns = schema["feature_columns"]
    categorical_columns = schema["categorical_columns"]

    missing_columns = [column for column in feature_columns if column not in dataset.columns]
    if missing_columns:
        raise ValueError(f"Dataset is missing required feature columns: {missing_columns}")

    features = dataset[feature_columns].copy()
    for column in categorical_columns:
        features[column] = features[column].fillna("UNKNOWN").astype("category")

    numeric_columns = [column for column in feature_columns if column not in categorical_columns]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    return features


def print_metric_summary(dataset: pd.DataFrame, predictions: np.ndarray) -> None:
    target = dataset[TARGET_COLUMN].to_numpy()
    mse = mean_squared_error(target, predictions)
    print("## Overall Metrics")
    print(f"Rows: {len(dataset)}")
    print(f"MAE : {mean_absolute_error(target, predictions):.6f}")
    print(f"RMSE: {np.sqrt(mse):.6f}")
    print(f"R2  : {r2_score(target, predictions):.6f}")


def print_score_distribution(dataset: pd.DataFrame) -> None:
    print("\n## Score Distribution")
    print(dataset[[TARGET_COLUMN, "predicted_score"]].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())


def print_group_summary(dataset: pd.DataFrame) -> None:
    print("\n## Group Checks")
    for column in GROUP_COLUMNS:
        if column not in dataset.columns:
            continue
        summary = (
            dataset.groupby(column, dropna=False)
            .agg(
                count=("predicted_score", "size"),
                actual_avg=(TARGET_COLUMN, "mean"),
                predicted_avg=("predicted_score", "mean"),
                predicted_min=("predicted_score", "min"),
                predicted_max=("predicted_score", "max"),
            )
            .reset_index()
        )
        print(f"\n### {column}")
        print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


def print_reject_reason_summary(dataset: pd.DataFrame, top: int) -> None:
    if "reject_reason" not in dataset.columns:
        return
    rejected = dataset[dataset["reject_reason"].notna() & (dataset["reject_reason"].astype(str).str.len() > 0)]
    if rejected.empty:
        return
    summary = (
        rejected.groupby("reject_reason")
        .agg(
            count=("predicted_score", "size"),
            actual_avg=(TARGET_COLUMN, "mean"),
            predicted_avg=("predicted_score", "mean"),
        )
        .sort_values("count", ascending=False)
        .head(top)
        .reset_index()
    )
    print("\n## Top Reject Reasons")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


def print_feature_importance(schema: dict[str, Any], top: int) -> None:
    importance = schema.get("feature_importance_top20", [])[:top]
    if not importance:
        return
    print("\n## Feature Importance")
    for row in importance:
        print(f"- {row['feature']}: {row['importance']:.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the trained LightGBM schedule scoring model.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Trained LightGBM model path.")
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH, help="Feature schema JSON path.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Training samples CSV path.")
    parser.add_argument("--top", type=int, default=10, help="Top N rows for summaries.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}. Run train_lightgbm.py first.")

    schema = load_schema(args.schema)
    dataset = load_dataset(args.data)
    features = build_features(dataset, schema)

    booster = lgb.Booster(model_file=str(args.model))
    predictions = np.clip(booster.predict(features), 0.0, 1.0)
    dataset = dataset.copy()
    dataset["predicted_score"] = predictions

    print_metric_summary(dataset, predictions)
    print_score_distribution(dataset)
    print_group_summary(dataset)
    print_reject_reason_summary(dataset, args.top)
    print_feature_importance(schema, args.top)


if __name__ == "__main__":
    main()
