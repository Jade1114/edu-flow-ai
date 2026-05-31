"""训练 LightGBM Placement Scorer + Room Ranker。

从 training_samples.csv 读取特征，训练 LightGBM 模型。
输出两个模型文件用于替换 V2 engine 中的规则版评分器。

用法：
    python3 ml/training/train_v2_scorer.py
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "models" / "v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LABEL = "label"
FEATURES = [
    "teacher_cross_count", "teacher_tasks", "student_count", "room_capacity",
    "capacity_ratio", "is_early", "is_late", "is_weekend", "day_of_week",
    "period_index", "period_count", "teacher_slot_count", "class_slot_count",
    "room_slot_count", "same_day_count",
]


def train():
    print("📥 加载训练数据...")
    df = pd.read_csv(DATA / "training_samples.csv")
    print(f"   样本数: {len(df)}, 正样本: {(df[LABEL] == 1).sum()}, "
          f"负样本: {(df[LABEL] == 0).sum()}")

    X = df[FEATURES]
    y = df[LABEL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"   训练集: {len(X_train)}, 测试集: {len(X_test)}")

    print("\n⚙️ 训练 LightGBM...")
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": 0,
        "num_threads": 4,
    }

    model = lgb.train(
        params,
        train_data,
        valid_sets=[test_data],
        num_boost_round=200,
        callbacks=[lgb.early_stopping(10), lgb.log_evaluation(50)],
    )

    # 评估
    y_pred = model.predict(X_test)
    auc = roc_auc_score(y_test, y_pred)
    acc = accuracy_score(y_test, (y_pred > 0.5).astype(int))
    print(f"\n📊 评估结果:")
    print(f"   AUC: {auc:.4f}")
    print(f"   Accuracy: {acc:.4f}")

    # 特征重要性
    importance = pd.DataFrame({
        "feature": FEATURES,
        "gain": model.feature_importance(importance_type="gain"),
        "split": model.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    print(f"\n📊 特征重要性:")
    print(importance.to_string(index=False))

    # 保存模型
    model_path = OUTPUT_DIR / "placement_scorer.txt"
    model.save_model(str(model_path))
    print(f"\n✅ 模型保存: {model_path}")

    # 保存特征 schema
    schema = {
        "features": FEATURES,
        "label": LABEL,
        "model_path": str(model_path),
        "model_type": "lightgbm_binary",
        "auc": round(auc, 4),
        "accuracy": round(acc, 4),
        "training_samples": len(df),
    }
    schema_path = OUTPUT_DIR / "feature_schema.json"
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"✅ Schema: {schema_path}")


if __name__ == "__main__":
    train()
