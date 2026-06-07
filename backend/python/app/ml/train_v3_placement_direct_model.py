"""Train a direct multiclass V3 placement model.

Model contract:
  input  = teaching-task features
  output = resource_key = classroom_name | day_of_week | period_index
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "real-dataset" / "v3_placement_direct_training_samples_clean.csv"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "models" / "v3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LABEL = "label_id"
RESOURCE_KEY = "resource_key"

FEATURES = [
    "course_name_code",
    "course_code_code",
    "teacher_no_code",
    "teacher_name_code",
    "class_name_code",
    "class_major_code",
    "class_department_code",
    "class_grade",
    "class_no",
    "student_count",
    "total_hours",
    "course_type_code",
    "required_room_type_code",
]


def train(data_path: Path = DATA_PATH) -> Path:
    if not data_path.exists():
        raise FileNotFoundError(f"Direct placement training samples not found: {data_path}")
    raw_df = pd.read_csv(data_path)
    raw_df.columns = [str(column).strip() for column in raw_df.columns]
    for column in raw_df.select_dtypes(include="object").columns:
        raw_df[column] = raw_df[column].astype(str).str.strip()
    resource_keys = sorted(raw_df[RESOURCE_KEY].astype(str).unique())
    label_by_resource = {key: index for index, key in enumerate(resource_keys)}
    df = _build_feature_frame(raw_df, label_by_resource)
    print(
        f"加载 Direct placement 样本: {data_path}\n"
        f"样本数: {len(df)}, source_key: {df['source_key'].nunique()}, resource_key: {len(resource_keys)}"
    )

    train_idx, test_idx = _group_split(df)
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()
    x_train = train_df[FEATURES]
    y_train = train_df[LABEL]
    x_test = test_df[FEATURES]
    y_test = test_df[LABEL]
    print(f"训练集: {len(train_df)}, 测试集: {len(test_df)}")

    train_data = lgb.Dataset(x_train, label=y_train)
    test_data = lgb.Dataset(x_test, label=y_test, reference=train_data)
    params = {
        "objective": "multiclass",
        "metric": "multi_logloss",
        "num_class": len(resource_keys),
        "boosting_type": "gbdt",
        "num_leaves": 63,
        "learning_rate": 0.04,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.85,
        "bagging_freq": 5,
        "min_child_samples": 10,
        "verbose": -1,
        "num_threads": 4,
    }
    model = lgb.train(
        params,
        train_data,
        valid_sets=[test_data],
        num_boost_round=400,
        callbacks=[lgb.early_stopping(25), lgb.log_evaluation(50)],
    )

    probabilities = model.predict(x_test)
    hit_metrics = _hit_at_k(test_df, probabilities, ks=(1, 5, 10, 30))
    print("评估结果:")
    for key, value in hit_metrics.items():
        print(f"{key}: {value:.4f}")

    model_path = OUTPUT_DIR / "placement_direct_model.txt"
    model.save_model(str(model_path))
    labels_path = OUTPUT_DIR / "placement_direct_labels.json"
    labels = {
        "label_by_resource": label_by_resource,
        "resource_by_label": {str(index): key for key, index in label_by_resource.items()},
        "resources": [_resource_meta(key) for key in resource_keys],
    }
    labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

    schema = {
        "model_type": "lightgbm_multiclass_v3_placement_direct_model",
        "model_path": str(model_path),
        "labels_path": str(labels_path),
        "training_data": str(data_path),
        "label": LABEL,
        "features": FEATURES,
        "contract": {
            "input": [
                "course_name",
                "course_code",
                "teacher_no",
                "teacher_name",
                "class_name",
                "course_type",
                "required_room_type",
                "student_count",
            ],
            "output": ["classroom_name", "day_of_week", "period_index"],
        },
        "metrics": {key: round(float(value), 4) for key, value in hit_metrics.items()},
        "training_samples": int(len(df)),
        "source_key_count": int(df["source_key"].nunique()),
        "resource_key_count": int(len(resource_keys)),
        "notes": "Direct placement model predicts resource_key without enumerating rooms x slots.",
    }
    schema_path = OUTPUT_DIR / "placement_direct_schema.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    importance = pd.DataFrame({
        "feature": FEATURES,
        "gain": model.feature_importance(importance_type="gain"),
        "split": model.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    importance_path = OUTPUT_DIR / "placement_direct_feature_importance.csv"
    importance.to_csv(importance_path, index=False)
    print(f"模型保存: {model_path}")
    print(f"Schema: {schema_path}")
    print(f"Labels: {labels_path}")
    print(f"Feature importance: {importance_path}")
    return model_path


def _build_feature_frame(raw_df: pd.DataFrame, label_by_resource: dict[str, int]) -> pd.DataFrame:
    df = raw_df.copy()
    for col in [
        "course_name", "course_code", "teacher_no", "teacher_name", "class_name",
        "class_major", "class_department", "course_type", "required_room_type",
    ]:
        df[f"{col}_code"] = df[col].map(_stable_code).astype(float)
    for col in ["class_grade", "class_no", "student_count", "total_hours"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df[LABEL] = df[RESOURCE_KEY].map(label_by_resource).astype(int)
    return df


def _group_split(df: pd.DataFrame):
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    return next(splitter.split(df, df[LABEL], groups=df["source_key"].astype(str)))


def _hit_at_k(test_df: pd.DataFrame, probabilities, *, ks: tuple[int, ...]) -> dict[str, float]:
    scored = test_df[["source_key", LABEL]].copy()
    hits = {k: 0 for k in ks}
    total = 0
    for _source_key, group in scored.groupby("source_key", dropna=False):
        truth = set(int(value) for value in group[LABEL].tolist())
        if not truth:
            continue
        total += 1
        row_index = group.index[0]
        probs = probabilities[test_df.index.get_loc(row_index)]
        ranked = sorted(range(len(probs)), key=lambda index: float(probs[index]), reverse=True)
        for k in ks:
            if truth & set(ranked[:k]):
                hits[k] += 1
    denominator = max(1, total)
    return {f"hit@{k}": hits[k] / denominator for k in ks}


def _resource_meta(resource_key: str) -> dict[str, Any]:
    room, day, period = resource_key.split("|")
    return {
        "resource_key": resource_key,
        "classroom_name": room,
        "day_of_week": int(day),
        "period_index": int(period),
    }


def _stable_code(value: Any, modulo: int = 10007) -> int:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1


if __name__ == "__main__":
    train()
