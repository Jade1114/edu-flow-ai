"""Direct V3 placement model inference helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "v3"
DIRECT_MODEL_PATH = MODEL_DIR / "placement_direct_model.txt"
DIRECT_SCHEMA_PATH = MODEL_DIR / "placement_direct_schema.json"
DIRECT_LABELS_PATH = MODEL_DIR / "placement_direct_labels.json"


class DirectPlacementModel:
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


def direct_features(row: dict[str, Any]) -> dict[str, float]:
    encoded = {
        "course_name_code": _stable_code(row.get("course_name")),
        "course_code_code": _stable_code(row.get("course_code")),
        "teacher_no_code": _stable_code(row.get("teacher_no")),
        "teacher_name_code": _stable_code(row.get("teacher_name")),
        "class_name_code": _stable_code(row.get("class_name") or row.get("class_group_names")),
        "class_major_code": _stable_code(row.get("class_major") or row.get("class_group_majors")),
        "class_department_code": _stable_code(row.get("class_department") or row.get("class_group_departments")),
        "course_type_code": _stable_code(row.get("course_type")),
        "required_room_type_code": _stable_code(row.get("required_room_type")),
    }
    numeric = {
        "class_grade": float(_first_int(row.get("class_grade") or row.get("class_group_grades"))),
        "class_no": float(_extract_class_no(str(row.get("class_name") or row.get("class_group_names") or ""))),
        "student_count": float(row.get("student_count") or row.get("total_student_count") or 0),
        "total_hours": float(row.get("total_hours") or 0),
    }
    return {**encoded, **numeric}


def parse_resource_key(resource_key: str) -> tuple[str, int, int] | None:
    parts = resource_key.split("|")
    if len(parts) != 3:
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _stable_code(value: Any, modulo: int = 10007) -> int:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1


def _first_int(value: Any) -> int:
    for part in str(value or "").split(","):
        try:
            return int(float(part.strip()))
        except ValueError:
            continue
    return 0


def _extract_class_no(value: str) -> int:
    if "班" not in value:
        return 0
    before = value.split("班")[0]
    digits = ""
    for char in reversed(before):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return int(digits) if digits else 0
