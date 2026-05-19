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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ml_logger
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "training" / "samples.csv"
MODEL_PATH = ROOT_DIR / "models" / "base" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "training" / "feature_schema.json"
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

    if "sample_weight" in dataset.columns:
        sample_weight = pd.to_numeric(dataset["sample_weight"], errors="coerce").fillna(1.0)
    else:
        sample_weight = pd.Series(np.ones(len(dataset)), index=dataset.index)

    return features, target, sample_weight, feature_columns, categorical_columns


def train_model(features: pd.DataFrame, target: pd.Series, sample_weight: pd.Series, categorical_columns: list[str]) -> tuple[lgb.LGBMRegressor, pd.DataFrame, pd.Series, pd.Series, dict[str, float]]:
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
    return model, x_test, y_test, predictions, metrics


def evaluate_validation(
    y_true: pd.Series,
    y_pred: pd.Series | np.ndarray,
) -> dict[str, Any]:
    """Compute validation metrics, both regression and ranking-oriented.

    For feedback samples (target is 0/1), also computes AUC and
    score_separation — how well the model distinguishes good from bad.
    """
    y_true = pd.Series(y_true).reset_index(drop=True)
    y_pred = pd.Series(np.asarray(y_pred)).reset_index(drop=True)

    val: dict[str, Any] = {}
    val["mae"] = float(mean_absolute_error(y_true, y_pred))
    val["rmse"] = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    val["r2"] = float(r2_score(y_true, y_pred))

    # If targets look binary (mostly 0/1), compute ranking metrics too
    unique_vals = y_true.dropna().unique()
    is_binary = set(unique_vals).issubset({0.0, 1.0, 0, 1}) and len(unique_vals) <= 2

    if is_binary:
        pos = y_pred[y_true >= 0.5]
        neg = y_pred[y_true < 0.5]
        val["score_separation"] = float(pos.mean() - neg.mean()) if len(pos) > 0 and len(neg) > 0 else 0.0
        val["pos_mean"] = float(pos.mean()) if len(pos) > 0 else 0.0
        val["neg_mean"] = float(neg.mean()) if len(neg) > 0 else 0.0

        from sklearn.metrics import roc_auc_score
        try:
            val["auc"] = float(roc_auc_score(y_true, y_pred))
        except Exception:
            val["auc"] = None

        # Score distribution buckets
        bins = [0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99, 0.999, 1.001]
        labels = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-0.9", "0.9-0.95", "0.95-0.99", "0.99-0.999", "0.999-1.0"]
        val["score_distribution"] = [
            {"range": labels[i], "count": int(c), "pct": round(float(c) / len(y_pred) * 100, 1)}
            for i, c in enumerate(np.histogram(y_pred, bins=bins)[0])
        ]

    # Score std dev — lower = more saturated
    val["score_std"] = float(y_pred.std())

    return val


def save_artifacts(
    model: lgb.LGBMRegressor,
    *,
    metrics: dict[str, float],
    validation: dict[str, Any] | None,
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
        "validation": validation,
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
    ml_logger.training_start({
        "data_path": str(args.data),
        "model_path": str(args.model),
        "schema_path": str(args.schema),
        "model_params": MODEL_PARAMS,
        "train_test_split": TRAIN_TEST_SPLIT,
    })

    dataset = load_dataset(args.data)
    features, target, sample_weight, feature_columns, categorical_columns = build_feature_frame(dataset)
    model, x_test, y_test, predictions, metrics = train_model(features, target, sample_weight, categorical_columns)
    validation = evaluate_validation(y_test, predictions)
    save_artifacts(
        model,
        metrics=metrics,
        validation=validation,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        data_path=args.data,
        model_path=args.model,
        feature_schema_path=args.schema,
    )

    # Log feature importance from the saved schema
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    importance = {row["feature"]: row["importance"] for row in schema.get("feature_importance_top20", [])}
    ml_logger.training_feature_importance(importance)
    ml_logger.training_complete(metrics, str(args.model))

    print(f"Trained LightGBM schedule scorer with {len(dataset)} samples")
    print(f"Features: {len(feature_columns)} total, {len(categorical_columns)} categorical")
    print(f"Metrics: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, R2={metrics['r2']:.4f}")
    if validation.get("auc") is not None:
        print(f"Validation AUC={validation['auc']:.4f},  score_separation={validation.get('score_separation', '-'):.4f},  score_std={validation['score_std']:.4f}")
    else:
        print(f"Validation score_std={validation['score_std']:.4f}")
    print(f"Model saved -> {args.model}")
    print(f"Feature schema saved -> {args.schema}")


if __name__ == "__main__":
    main()
