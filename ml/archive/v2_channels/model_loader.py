"""LightGBM 模型加载器 — 为 V2 engine 提供 ML 版评分。

读取 ml/models/v2/ 下的模型文件，替换规则版 scorer。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger("v2.model")

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models" / "v2"
MODEL_PATH = MODEL_DIR / "placement_scorer.txt"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"

_model = None
_schema = None


def load() -> bool:
    """加载 LightGBM 模型。返回是否成功。"""
    global _model, _schema

    if not MODEL_PATH.exists():
        _log.warning("V2 模型不存在: %s，使用规则版", MODEL_PATH)
        return False

    import lightgbm as lgb

    _model = lgb.Booster(model_file=str(MODEL_PATH))
    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH) as f:
            _schema = json.load(f)

    _log.info("✅ V2 模型加载: %s (AUC=%s)", MODEL_PATH, _schema.get("auc", "?") if _schema else "?")
    return True


def predict(features: dict) -> float:
    """对单个 Placement (task, slot, room) 预测评分。

    Args:
        features: 与训练特征一致的 dict

    Returns:
        0~1 的评分，越高越好
    """
    if _model is None:
        return 0.5  # 无模型时返回中性分

    feats = _schema["features"] if _schema else list(features.keys())
    row = [[features.get(f, 0) for f in feats]]
    prob = _model.predict(row)[0]
    return float(prob)


def predict_batch(rows: list[dict]) -> list[float]:
    """批量预测。"""
    if _model is None:
        return [0.5] * len(rows)

    feats = _schema["features"] if _schema else list(rows[0].keys())
    import pandas as pd
    df = pd.DataFrame(rows)[feats]
    return [float(p) for p in _model.predict(df)]


def is_loaded() -> bool:
    return _model is not None


# 模块导入时自动加载
loaded = load()
