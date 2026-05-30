"""Train the first LightGBM schedule scoring model.

Input:
    ../data/base/samples.csv

Outputs:
    ../models/base/schedule_ranker_v1.txt
    ../models/base/feature_schema.json
"""

from __future__ import annotations

import json
from pathlib import Path

from ml import ml_logger
from ml.training.config import (
    CATEGORICAL_COLUMNS,
    DATA_PATH,
    EXCLUDED_COLUMNS,
    FEATURE_SCHEMA_PATH,
    MODEL_PARAMS,
    MODEL_PATH,
    TARGET_COLUMN,
    TRAIN_TEST_SPLIT,
)
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


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


def train_model(
    features: pd.DataFrame,
    target: pd.Series,
    sample_weight: pd.Series,
    categorical_columns: list[str],
    model_params: dict[str, Any] | None = None,
) -> tuple[lgb.LGBMRegressor, pd.DataFrame, pd.Series, pd.Series, dict[str, float]]:
    x_train, x_test, y_train, y_test, weight_train, _ = train_test_split(
        features,
        target,
        sample_weight,
        **TRAIN_TEST_SPLIT,
    )

    effective_model_params = {**MODEL_PARAMS, **(model_params or {})}
    model = lgb.LGBMRegressor(**effective_model_params)
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


def _resolve_training_data_path(training_data_dir: str | None) -> Path:
    if not training_data_dir:
        return DATA_PATH
    data_path = Path(training_data_dir)
    return data_path / "samples.csv" if data_path.is_dir() else data_path


def run_training_pipeline(
    training_data_dir: str | None = None,
    output_model_path: str | None = None,
    output_schema_path: str | None = None,
    **training_params: Any,
) -> dict[str, Any]:
    data_path = _resolve_training_data_path(training_data_dir)
    model_path = Path(output_model_path) if output_model_path else MODEL_PATH
    schema_path = Path(output_schema_path) if output_schema_path else FEATURE_SCHEMA_PATH

    effective_model_params = {**MODEL_PARAMS, **training_params}
    ml_logger.training_start({
        "data_path": str(data_path),
        "model_path": str(model_path),
        "schema_path": str(schema_path),
        "model_params": effective_model_params,
        "train_test_split": TRAIN_TEST_SPLIT,
    })

    dataset = load_dataset(data_path)
    features, target, sample_weight, feature_columns, categorical_columns = build_feature_frame(dataset)
    model, _x_test, y_test, predictions, metrics = train_model(
        features,
        target,
        sample_weight,
        categorical_columns,
        effective_model_params,
    )
    validation = evaluate_validation(y_test, predictions)
    save_artifacts(
        model,
        metrics=metrics,
        validation=validation,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        data_path=data_path,
        model_path=model_path,
        feature_schema_path=schema_path,
    )

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    importance = {row["feature"]: row["importance"] for row in schema.get("feature_importance_top20", [])}
    ml_logger.training_feature_importance(importance)
    ml_logger.training_complete(metrics, str(model_path))

    return {
        "model_path": str(model_path),
        "schema_path": str(schema_path),
        "metrics": metrics,
        "validation": validation,
        "sample_count": len(dataset),
        "feature_count": len(feature_columns),
        "categorical_feature_count": len(categorical_columns),
    }

