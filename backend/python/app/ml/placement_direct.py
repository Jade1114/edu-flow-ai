"""Direct V3 placement model inference helpers.

Supports both LightGBM (single stage) and CatBoost (two-stage) models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parents[3] / "models"
DIRECT_MODEL_PATH = MODEL_DIR / "placement_direct_model.txt"
DIRECT_SCHEMA_PATH = MODEL_DIR / "placement_direct_schema.json"
DIRECT_LABELS_PATH = MODEL_DIR / "placement_direct_labels.json"
CATBOOST_META_PATH = MODEL_DIR / "catboost_meta.json"


class DirectPlacementModel:
    """LightGBM single-stage placement model (original)."""

    def __init__(
        self,
        model: lgb.Booster,
        features: list[str],
        resource_by_label: dict[int, str],
    ) -> None:
        self.model = model
        self.features = features
        self.resource_by_label = resource_by_label

    @classmethod
    def load(cls) -> "DirectPlacementModel":
        if not DIRECT_MODEL_PATH.exists() or not DIRECT_SCHEMA_PATH.exists() or not DIRECT_LABELS_PATH.exists():
            raise FileNotFoundError("V3 direct placement model artifacts are missing.")
        schema = json.loads(DIRECT_SCHEMA_PATH.read_text(encoding="utf-8"))
        labels = json.loads(DIRECT_LABELS_PATH.read_text(encoding="utf-8"))
        resource_by_label = {int(key): value for key, value in labels["resource_by_label"].items()}
        return cls(
            model=lgb.Booster(model_file=str(DIRECT_MODEL_PATH)),
            features=list(schema["features"]),
            resource_by_label=resource_by_label,
        )

    def predict_topk(self, task_like: dict[str, Any], *, top_k: int) -> list[tuple[str, float]]:
        frame = pd.DataFrame([direct_features(task_like)], columns=self.features)
        probabilities = self.model.predict(frame)[0]
        ranked_indexes = sorted(range(len(probabilities)), key=lambda index: float(probabilities[index]), reverse=True)
        result: list[tuple[str, float]] = []
        for label_id in ranked_indexes[:top_k]:
            resource_key = self.resource_by_label.get(int(label_id))
            if resource_key:
                result.append((resource_key, float(probabilities[label_id])))
        return result


class CatBoostPlacementModel:
    """CatBoost two-stage model: stage1 predicts (day,period), stage2 predicts room."""

    def __init__(self, stage1, stage2_models: dict, meta: dict):
        self.stage1 = stage1
        self.stage2_models = stage2_models
        self.meta = meta
        self.features = meta["stage1_features"]
        self.cat_features = meta["stage1_cat_features"]

    @classmethod
    def load(cls) -> "CatBoostPlacementModel":
        from catboost import CatBoostClassifier

        if not CATBOOST_META_PATH.exists():
            raise FileNotFoundError(f"CatBoost meta not found: {CATBOOST_META_PATH}")

        meta = json.loads(CATBOOST_META_PATH.read_text(encoding="utf-8"))
        stage1 = CatBoostClassifier()
        stage1.load_model(meta["stage1_path"])

        stage2_models: dict[str, Any] = {}
        for slot, info in meta["stage2_models"].items():
            m = CatBoostClassifier()
            m.load_model(info["path"])
            stage2_models[slot] = m

        return cls(stage1, stage2_models, meta)

    def predict_topk(self, task_like: dict[str, Any], *, top_k: int) -> list[tuple[str, float]]:
        from catboost import Pool as CatPool

        row = {f: str(task_like.get(f, "")) for f in self.cat_features}
        for f in self.features:
            if f not in self.cat_features:
                row[f] = float(task_like.get(f, 0))

        pool = CatPool(pd.DataFrame([row]), cat_features=self.cat_features)

        # Stage 1: 取所有 35 个时段，按概率降序
        proba = self.stage1.predict_proba(pool)[0]
        all_slots = sorted(zip(self.stage1.classes_, proba), key=lambda x: -x[1])
        # 取概率最高的前 30 个时段（覆盖 86% 的类别），留空样本冷却时段
        top_slots = [(s, p) for s, p in all_slots if s in self.stage2_models][:max(20, min(30, top_k))]

        candidates: list[tuple[str, float]] = []
        valid_slots = [(s, p) for s, p in top_slots if s in self.stage2_models]
        if not valid_slots:
            return []
        n_per_slot = top_k // len(valid_slots) or 1
        remainder = top_k - n_per_slot * len(valid_slots)
        for idx, (slot, slot_prob) in enumerate(valid_slots):
            m2 = self.stage2_models[slot]
            proba2 = m2.predict_proba(pool)[0]
            rclasses = m2.classes_
            extra = 1 if idx < remainder else 0
            top_rooms = sorted(zip(rclasses, proba2), key=lambda x: -x[1])[:n_per_slot + extra]
            day, period = slot.split("|")
            for room, room_prob in top_rooms:
                candidates.append((f"{room}|{day}|{period}", slot_prob * room_prob))

        candidates.sort(key=lambda x: -x[1])
        return candidates[:top_k]


def direct_features(task_like: dict[str, Any]) -> dict[str, float]:
    """Encode a teaching task into the 13 LightGBM feature vector."""
    def stable_code(value: Any, modulo: int = 10007) -> float:
        text = str(value or "").strip().lower().replace(" ", "")
        if not text:
            return 0.0
        total = 0
        for char in text:
            total = (total * 131 + ord(char)) % modulo
        return float(total + 1)

    def _first_int(value: Any) -> int:
        for part in str(value or "").split(","):
            try:
                return int(float(part.strip()))
            except (TypeError, ValueError):
                continue
        return 0

    return {
        "course_name_code": stable_code(task_like.get("course_name")),
        "course_code_code": stable_code(task_like.get("course_code")),
        "teacher_no_code": stable_code(task_like.get("teacher_no")),
        "teacher_name_code": stable_code(task_like.get("teacher_name")),
        "class_name_code": stable_code(task_like.get("class_name") or task_like.get("class_group_names")),
        "class_major_code": stable_code(task_like.get("class_major") or task_like.get("class_group_majors")),
        "class_department_code": stable_code(task_like.get("class_department") or task_like.get("class_group_departments")),
        "class_grade": float(_first_int(task_like.get("class_grade") or task_like.get("class_group_grades"))),
        "class_no": 0.0,
        "student_count": float(task_like.get("student_count") or 0),
        "total_hours": float(task_like.get("total_hours") or 0),
        "course_type_code": stable_code(task_like.get("course_type")),
        "required_room_type_code": stable_code(task_like.get("required_room_type")),
    }


def parse_resource_key(key: str) -> tuple[str, int, int] | None:
    """Parse 'classroom_name|day|period' into components."""
    parts = key.split("|")
    if len(parts) != 3:
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        return None
