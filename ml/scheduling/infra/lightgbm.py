"""LightGBM loading and feature-building helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
except ImportError:
    lgb = None


def load_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"Feature schema not found: {schema_path}. Run train_lightgbm.py first.")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_optional_lightgbm(model_path: Path, schema_path: Path):
    """Load LightGBM booster + schema or return None fallback."""
    if lgb is None:
        return None, None, "rule_score_fallback"
    if model_path.exists() and schema_path.exists():
        return lgb.Booster(model_file=str(model_path)), load_schema(schema_path), "lightgbm"

    missing = []
    if not model_path.exists():
        missing.append(str(model_path))
    if not schema_path.exists():
        missing.append(str(schema_path))
    return None, None, "rule_score_fallback"


def build_features(rows: list[dict[str, Any]], schema: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    feature_columns = schema["feature_columns"]
    categorical_columns = schema["categorical_columns"]
    if "sample_weight" in feature_columns and "sample_weight" not in frame.columns:
        frame["sample_weight"] = 1.0
    missing_columns = [col for col in feature_columns if col not in frame.columns]
    if missing_columns:
        raise ValueError(f"Candidate rows are missing required feature columns: {missing_columns}")

    features = frame[feature_columns].copy()
    for col in categorical_columns:
        features[col] = features[col].fillna("UNKNOWN").astype("category")
    numeric_columns = [col for col in feature_columns if col not in categorical_columns]
    for col in numeric_columns:
        features[col] = pd.to_numeric(features[col], errors="coerce").fillna(0)
    return features
