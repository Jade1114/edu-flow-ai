"""Train the first LightGBM schedule scoring model.

Input:
    ../data/training_samples.csv

Outputs:
    ../models/schedule_ranker_v1.txt
    ../data/feature_schema.json
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
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "training_samples.csv"
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"
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


def load_dataset(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(
            f"Training samples not found: {data_path}. "
            "Run generate_training_samples.py first."
        )
    dataset = pd.read_csv(data_path)
    if dataset.empty:
        raise ValueError(f"Training samples are empty: {data_path}")
    if TARGET_COLUMN not in dataset.columns:
        raise ValueError(f"Target column `{TARGET_COLUMN}` is missing from {data_path}")
    return dataset


def build_feature_frame(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series, list[str], list[str]]:
    feature_columns = [column for column in dataset.columns if column not in EXCLUDED_COLUMNS]
    categorical_columns = [column for column in CATEGORICAL_COLUMNS if column in feature_columns]
    features = dataset[feature_columns].copy()

    for column in categorical_columns:
        features[column] = features[column].fillna("UNKNOWN").astype("category")

    numeric_columns = [column for column in feature_columns if column not in categorical_columns]
    for column in numeric_columns:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    target = pd.to_numeric(dataset[TARGET_COLUMN], errors="coerce")
    if target.isna().any():
        raise ValueError(f"Target column `{TARGET_COLUMN}` contains non-numeric values")

    sample_weight = pd.to_numeric(dataset.get("sample_weight", 1.0), errors="coerce").fillna(1.0)

    return features, target, sample_weight, feature_columns, categorical_columns


def train_model(features: pd.DataFrame, target: pd.Series, sample_weight: pd.Series, categorical_columns: list[str]) -> tuple[lgb.LGBMRegressor, dict[str, float]]:
    x_train, x_test, y_train, y_test, weight_train, _ = train_test_split(
        features,
        target,
        sample_weight,
        **TRAIN_TEST_SPLIT,
    )

    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(
        x_train,
        y_train,
        sample_weight=weight_train,
        categorical_feature=categorical_columns,
        eval_set=[(x_test, y_test)],
        eval_metric="l2",
        callbacks=[lgb.log_evaluation(period=0)],
    )

    predictions = np.clip(model.predict(x_test), 0.0, 1.0)
    mse = mean_squared_error(y_test, predictions)
    metrics = {
        "mae": float(mean_absolute_error(y_test, predictions)),
        "mse": float(mse),
        "rmse": float(np.sqrt(mse)),
        "r2": float(r2_score(y_test, predictions)),
    }
    return model, metrics


def save_artifacts(
    model: lgb.LGBMRegressor,
    *,
    metrics: dict[str, float],
    feature_columns: list[str],
    categorical_columns: list[str],
    data_path: Path,
    model_path: Path,
    feature_schema_path: Path,
) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    feature_schema_path.parent.mkdir(parents=True, exist_ok=True)

    booster = model.booster_
    booster.save_model(str(model_path))

    feature_importance = booster.feature_importance(importance_type="gain")
    importance_rows = sorted(
        (
            {"feature": feature, "importance": float(importance)}
            for feature, importance in zip(feature_columns, feature_importance)
        ),
        key=lambda row: row["importance"],
        reverse=True,
    )

    schema: dict[str, Any] = {
        "version": "schedule_ranker_v1",
        "model_type": "lightgbm_regressor",
        "target_column": TARGET_COLUMN,
        "data_path": str(data_path),
        "model_path": str(model_path),
        "model_params": MODEL_PARAMS,
        "train_test_split": TRAIN_TEST_SPLIT,
        "feature_columns": feature_columns,
        "categorical_columns": categorical_columns,
        "excluded_columns": sorted(EXCLUDED_COLUMNS),
        "metrics": metrics,
        "feature_importance_top20": importance_rows[:20],
    }
    feature_schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the first LightGBM schedule scoring model.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Training samples CSV path.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Output LightGBM model path.")
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH, help="Output feature schema JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = load_dataset(args.data)
    features, target, sample_weight, feature_columns, categorical_columns = build_feature_frame(dataset)
    model, metrics = train_model(features, target, sample_weight, categorical_columns)
    save_artifacts(
        model,
        metrics=metrics,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        data_path=args.data,
        model_path=args.model,
        feature_schema_path=args.schema,
    )

    print(f"Trained LightGBM schedule scorer with {len(dataset)} samples")
    print(f"Features: {len(feature_columns)} total, {len(categorical_columns)} categorical")
    print(f"Metrics: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, R2={metrics['r2']:.4f}")
    print(f"Model saved -> {args.model}")
    print(f"Feature schema saved -> {args.schema}")


if __name__ == "__main__":
    main()
