"""Train the LightGBM room ranker.

The trained model ranks classrooms for a teaching task. It does not score
day/period/template placements.
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from ml.scheduling_v2.room_ranker import ROOM_RANK_FEATURES
from ml.training.build_room_ranker_training_data import build as build_samples

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "models" / "v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES_PATH = DATA / "room_ranker_samples.csv"
LABEL = "label"


def train() -> Path:
    if not SAMPLES_PATH.exists():
        build_samples()

    print("加载 room ranker 训练数据...")
    df = pd.read_csv(SAMPLES_PATH)
    missing_features = [feature for feature in ROOM_RANK_FEATURES if feature not in df.columns]
    if missing_features:
        print(f"训练样本缺少特征 {missing_features}，重新生成...")
        build_samples()
        df = pd.read_csv(SAMPLES_PATH)
    print(
        f"样本数: {len(df)}, 正样本: {(df[LABEL] == 1).sum()}, "
        f"负样本: {(df[LABEL] == 0).sum()}"
    )

    y = df[LABEL]
    stratify = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None
    train_df, test_df = train_test_split(
        df,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )
    x_train = train_df[ROOM_RANK_FEATURES]
    y_train = train_df[LABEL]
    x_test = test_df[ROOM_RANK_FEATURES]
    y_test = test_df[LABEL]
    print(f"训练集: {len(x_train)}, 测试集: {len(x_test)}")

    train_data = lgb.Dataset(x_train, label=y_train)
    test_data = lgb.Dataset(x_test, label=y_test, reference=train_data)
    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.85,
        "bagging_fraction": 0.85,
        "bagging_freq": 5,
        "verbose": -1,
        "num_threads": 4,
    }
    print("训练 LightGBM room ranker...")
    model = lgb.train(
        params,
        train_data,
        valid_sets=[test_data],
        num_boost_round=200,
        callbacks=[lgb.early_stopping(10), lgb.log_evaluation(50)],
    )

    y_pred = model.predict(x_test)
    auc = roc_auc_score(y_test, y_pred) if y_test.nunique() > 1 else 0.0
    acc = accuracy_score(y_test, (y_pred > 0.5).astype(int))
    hit_metrics = _hit_at_k(test_df, y_pred, ks=(3, 5, 10))
    print("评估结果:")
    print(f"AUC: {auc:.4f}")
    print(f"Accuracy: {acc:.4f}")
    for key, value in hit_metrics.items():
        print(f"{key}: {value:.4f}")

    importance = pd.DataFrame({
        "feature": ROOM_RANK_FEATURES,
        "gain": model.feature_importance(importance_type="gain"),
        "split": model.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    print("特征重要性:")
    print(importance.to_string(index=False))

    model_path = OUTPUT_DIR / "room_ranker.txt"
    model.save_model(str(model_path))
    print(f"模型保存: {model_path}")

    schema = {
        "features": ROOM_RANK_FEATURES,
        "label": LABEL,
        "model_path": str(model_path),
        "model_type": "lightgbm_binary_room_ranker",
        "auc": round(float(auc), 4),
        "accuracy": round(float(acc), 4),
        **{key: round(float(value), 4) for key, value in hit_metrics.items()},
        "training_samples": int(len(df)),
        "notes": "teaching_task + classroom -> ranked classrooms; no day/period features",
    }
    schema_path = OUTPUT_DIR / "room_ranker_feature_schema.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2))
    print(f"Schema: {schema_path}")
    return model_path


def _hit_at_k(test_df: pd.DataFrame, predictions, *, ks: tuple[int, ...]) -> dict[str, float]:
    scored = test_df[["course_code", "class_group", "label", "room_name"]].copy()
    scored["prediction"] = predictions
    hits = {k: 0 for k in ks}
    total = 0
    for _key, group in scored.groupby(["course_code", "class_group"], dropna=False):
        if not (group["label"] == 1).any():
            continue
        total += 1
        positives = set(str(room) for room in group[group["label"] == 1]["room_name"])
        ranked = group.sort_values("prediction", ascending=False)
        for k in ks:
            top_rooms = set(str(room) for room in ranked.head(k)["room_name"])
            if positives & top_rooms:
                hits[k] += 1
    denominator = max(1, total)
    return {f"hit@{k}": hits[k] / denominator for k in ks}


if __name__ == "__main__":
    train()
