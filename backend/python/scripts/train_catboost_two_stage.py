#!/usr/bin/env python3
"""
CatBoost 两阶段 Placement Model 训练。

阶段 1: 预测 (天, 节次)     → 35 类
阶段 2: 对每个时段预测教室   → ~50 类

产出:
  backend/models/catboost_stage1.cbm
  backend/models/catboost_stage2_<slot>.cbm  (每个时段一个)
"""

import json, sys, pickle
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, Pool

DATA_DIR   = Path(__file__).resolve().parents[2] / "data"
PARSED_DIR = DATA_DIR / "parsed"
MODEL_DIR  = Path(__file__).resolve().parents[2] / "models"
ALLOC_PATH = DATA_DIR / "allocation_items.jsonl"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ── 特征列定义 ──────────────────────────────────────
CAT_FEATURES = [
    "course_code", "teacher_name", "course_type", "required_room_type",
    "class_major", "class_department",
]
NUM_FEATURES = ["class_grade", "student_count", "total_hours"]
ALL_FEATURES = CAT_FEATURES + NUM_FEATURES

# ── 加载数据 ────────────────────────────────────────
def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

def build_training_data():
    print("加载数据...")
    # 历史排课记录
    items = load_jsonl(ALLOC_PATH)
    print(f"  原始排课片段: {len(items)}")

    # 课程信息
    courses = {}
    for c in load_jsonl(PARSED_DIR / "courses.jsonl"):
        courses[c["code"]] = c

    # 班级信息
    class_groups = {}
    for cg in load_jsonl(PARSED_DIR / "class_groups.jsonl"):
        class_groups[cg["name"]] = cg

    # 拼接特征
    rows = []
    for item in items:
        code = item["course_code"]
        cls_name = item["class_group_name"]
        teacher = item.get("teacher_name", "").strip()
        room = item.get("room_name", "").strip()

        # 跳过缺失数据
        if not teacher or not room:
            continue
        # 跳过公共课（全校课，不涉及专业课排课）
        public_codes = {
            '形027','形029','形031','形033','形154',
            '思040','军010','毛927','中019',
            '大002','大003','大004','大006','大008','大035',
            '学312','工034','概037','沟048','高038',
        }
        if code in public_codes:
            continue

        course = courses.get(code, {})
        cg = class_groups.get(cls_name, {})

        rows.append({
            "course_code": code,
            "teacher_name": item.get("teacher_name", ""),
            "course_type": course.get("course_type", ""),
            "required_room_type": course.get("required_room_type", ""),
            "class_grade": int(cg.get("grade", 0)) if cg.get("grade") else 0,
            "class_major": cg.get("major", ""),
            "class_department": cg.get("department", ""),
            "student_count": int(cg.get("student_count", 0)),
            "total_hours": 0,
            "day_of_week": item["day_of_week"],
            "period_index": item["period_index"],
            "room_name": item["room_name"],
        })

    df = pd.DataFrame(rows)
    df["slot_label"] = df["day_of_week"].astype(str) + "|" + df["period_index"].astype(str)
    df["room_label"] = df["room_name"]

    # 去重：同一 (任务特征, slot) 只保留一次
    df = df.drop_duplicates(subset=["course_code","teacher_name","course_type",
                                     "class_major","class_department","slot_label"])
    print(f"  去重后: {len(df)} 条")

    # 分类编码
    df["slot_label"] = df["slot_label"].astype(str)
    df["room_label"] = df["room_label"].astype(str)

    # 填缺失值
    for c in CAT_FEATURES:
        df[c] = df[c].fillna("").astype(str)
    for c in NUM_FEATURES:
        df[c] = df[c].fillna(0).astype(int)

    print(f"  训练样本: {len(df)}")
    print(f"  时段类别数: {df['slot_label'].nunique()}")
    print(f"  时段分布:")
    for slot, cnt in df["slot_label"].value_counts().head(10).items():
        print(f"    {slot}: {cnt}")
    return df

# ── 阶段 1: 训练时段分类器 ──────────────────────────
def train_stage1(df):
    print("\n=== 阶段 1: 训练时段分类器 ===")
    
    X = df[ALL_FEATURES]
    y_slot = df["slot_label"]

    # 训练/测试划分（按 course_code 分组，防止同课程跨集）
    np.random.seed(42)
    codes = X["course_code"].unique()
    np.random.shuffle(codes)
    split = int(len(codes) * 0.85)
    train_codes = set(codes[:split])
    train_idx = X["course_code"].isin(train_codes)
    test_idx = ~train_idx

    X_train, y_train = X[train_idx], y_slot[train_idx]
    X_test, y_test = X[test_idx], y_slot[test_idx]
    print(f"  训练集: {len(X_train)}, 测试集: {len(X_test)}")

    train_pool = Pool(X_train, y_train, cat_features=CAT_FEATURES)
    test_pool = Pool(X_test, y_test, cat_features=CAT_FEATURES)

    model = CatBoostClassifier(
        iterations=300,
        depth=6,
        learning_rate=0.1,
        loss_function="MultiClass",
        auto_class_weights="Balanced",
        verbose=50,
        random_seed=42,
    )
    model.fit(train_pool, eval_set=test_pool, early_stopping_rounds=30)

    # 评估
    preds = model.predict(test_pool)
    pred_proba = model.predict_proba(test_pool)
    
    classes = model.classes_
    class_to_idx = {c: i for i, c in enumerate(classes)}

    hit1 = (preds.flatten() == y_test.values).mean()
    print(f"  hit@1: {hit1:.4f}")

    # hit@5
    hit5 = 0
    for i in range(len(X_test)):
        top5 = np.argsort(pred_proba[i])[::-1][:5]
        true_label = y_test.iloc[i]
        if class_to_idx.get(true_label) in top5:
            hit5 += 1
    print(f"  hit@5: {hit5/len(X_test):.4f}")

    model.save_model(str(MODEL_DIR / "catboost_stage1.cbm"))
    print(f"  模型保存: catboost_stage1.cbm")
    
    return model, class_to_idx

# ── 阶段 2: 对每个时段训教室分类器 ──────────────────
def train_stage2(df):
    print("\n=== 阶段 2: 训练时段子模型 ===")
    
    # 按 slot_label 分组
    slot_groups = defaultdict(list)
    for _, row in df.iterrows():
        slot_groups[row["slot_label"]].append(row)

    models = {}
    min_samples = 15

    for slot, rows in slot_groups.items():
        sdf = pd.DataFrame(rows)
        room_counts = sdf["room_label"].value_counts()
        if len(sdf) < min_samples:
            print(f"  跳过 {slot}: 仅 {len(sdf)} 条样本 < {min_samples}")
            continue
        
        X = sdf[ALL_FEATURES]
        y = sdf["room_label"]

        pool = Pool(X, y, cat_features=CAT_FEATURES)

        model = CatBoostClassifier(
            iterations=150,
            depth=5,
            learning_rate=0.1,
            loss_function="MultiClass",
            auto_class_weights="Balanced",
            verbose=0,
            random_seed=42,
        )
        model.fit(pool)

        room_classes = model.classes_
        path = MODEL_DIR / f"catboost_stage2_{slot.replace('|', '_')}.cbm"
        model.save_model(str(path))
        models[slot] = {
            "path": str(path),
            "classes": room_classes.tolist(),
            "n_rooms": len(room_classes),
            "n_samples": len(sdf),
        }

        print(f"  {slot}: {len(sdf)} 条, {len(room_classes)} 教室")

    # 保存元信息
    meta = {
        "stage1_path": str(MODEL_DIR / "catboost_stage1.cbm"),
        "stage1_features": ALL_FEATURES,
        "stage1_cat_features": CAT_FEATURES,
        "stage2_models": models,
        "n_slots": len(models),
        "total_slots": len(slot_groups),
    }
    with open(MODEL_DIR / "catboost_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n  阶段 2: {len(models)}/{len(slot_groups)} 个时段有模型")
    print(f"  元信息: catboost_meta.json")
    
    return models, meta

# ── 推理接口（验证用） ──────────────────────────────
def predict_topk(model_stage1, meta, task_row, top_k=30):
    """加载模型并推理 top-k (room, day, period) 候选"""
    from catboost import CatBoostClassifier, Pool
    
    stage1 = model_stage1
    
    # 读取阶段 2 模型
    stage2_models = {}
    for slot, info in meta["stage2_models"].items():
        m = CatBoostClassifier()
        m.load_model(info["path"])
        stage2_models[slot] = m

    # 阶段 1: 预测 top-N 时段
    pool = Pool(pd.DataFrame([task_row]), cat_features=meta["stage1_cat_features"])
    proba = stage1.predict_proba(pool)[0]
    classes = stage1.classes_
    top_slots = sorted(zip(classes, proba), key=lambda x: -x[1])[:5]

    candidates = []
    for slot, slot_prob in top_slots:
        # 阶段 2: 预测教室
        if slot not in stage2_models:
            continue
        m2 = stage2_models[slot]
        pool2 = Pool(pd.DataFrame([task_row]), cat_features=meta["stage1_cat_features"])
        proba2 = m2.predict_proba(pool2)[0]
        room_classes = m2.classes_
        top_rooms = sorted(zip(room_classes, proba2), key=lambda x: -x[1])[:top_k // len(top_slots)]

        day, period = slot.split("|")
        for room, room_prob in top_rooms:
            candidates.append((room, int(day), int(period), slot_prob * room_prob))

    candidates.sort(key=lambda x: -x[3])
    return candidates[:top_k]


# ── 主入口 ──────────────────────────────────────────
def main():
    print("=" * 50)
    print("CatBoost 两阶段模型训练")
    print("=" * 50)

    df = build_training_data()
    model, class_to_idx = train_stage1(df)
    models, meta = train_stage2(df)

    print("\n" + "=" * 50)
    print("训练完成 ✅")
    print(f"  阶段 1: {MODEL_DIR / 'catboost_stage1.cbm'}")
    print(f"  阶段 2: {len(meta['stage2_models'])} 个子模型")
    print(f"  元信息: {MODEL_DIR / 'catboost_meta.json'}")

if __name__ == "__main__":
    main()
