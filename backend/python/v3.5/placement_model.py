"""V3.5 two-stage placement model.

Contract:
  input  = teaching-task features
  output = TopK weekly-template placements: classroom_name | day_of_week | period_index
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = REPO_ROOT / "backend" / "data" / "training" / "v3_training_samples.csv"
OUTPUT_DIR = REPO_ROOT / "backend" / "data" / "pipeline" / "v3.5"
MODELS_DIR = REPO_ROOT / "backend" / "models" / "v3.5" / "placement"
META_PATH = MODELS_DIR / "placement_meta.json"
STAGE1_MODEL_PATH = MODELS_DIR / "stage1_slot.cbm"
STAGE2_DIR = MODELS_DIR / "stage2_slots"

SLOT_LABEL = "slot_label"
ROOM_LABEL = "classroom_name"
RESOURCE_KEY = "resource_key"

CATEGORICAL_FEATURES = [
    "course_name",
    "course_code",
    "teacher_no",
    "teacher_name",
    "class_name",
    "class_major",
    "class_department",
    "course_type",
    "required_room_type",
]
NUMERIC_FEATURES = ["class_grade", "class_no", "student_count", "total_hours"]
STAGE1_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
STAGE2_FEATURES = CATEGORICAL_FEATURES + [SLOT_LABEL] + NUMERIC_FEATURES
STAGE2_CATEGORICAL_FEATURES = CATEGORICAL_FEATURES + [SLOT_LABEL]


@dataclass(frozen=True)
class PlacementCandidate:
    resource_key: str
    classroom_name: str
    day_of_week: int
    period_index: int
    score: float
    slot_score: float
    room_score: float
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_key": self.resource_key,
            "classroom_name": self.classroom_name,
            "day_of_week": self.day_of_week,
            "period_index": self.period_index,
            "score": self.score,
            "slot_score": self.slot_score,
            "room_score": self.room_score,
            "source": self.source,
        }


class V35PlacementModel:
    def __init__(self, stage1: Any, slot_room_models: dict[str, Any], meta: dict[str, Any]) -> None:
        self.stage1 = stage1
        self.slot_room_models = slot_room_models
        self.meta = meta
        self.room_meta = meta.get("rooms", {})
        self.room_priors = meta.get("room_priors", {})

    @classmethod
    def load(cls, model_dir: Path = OUTPUT_DIR) -> "V35PlacementModel":
        CatBoostClassifier = _catboost_classifier()
        meta_path = model_dir / "placement_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"V3.5 placement meta not found: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        stage1 = CatBoostClassifier()
        stage1.load_model(meta["stage1_model_path"])

        slot_room_models: dict[str, Any] = {}
        for slot_label, info in meta.get("slot_room_models", {}).items():
            model = CatBoostClassifier()
            model.load_model(info["model_path"])
            slot_room_models[slot_label] = model

        return cls(stage1=stage1, slot_room_models=slot_room_models, meta=meta)

    def predict_topk(self, task_like: dict[str, Any], *, top_k: int = 40, slot_top_k: int = 10) -> list[PlacementCandidate]:
        base_row = _normalize_task_row(task_like)
        slot_frame = pd.DataFrame([base_row], columns=STAGE1_FEATURES)
        slot_pool = _catboost_pool(slot_frame, CATEGORICAL_FEATURES)
        slot_probabilities = self.stage1.predict_proba(slot_pool)[0]
        ranked_slots = _rank_classes(self.stage1.classes_, slot_probabilities)[:slot_top_k]

        candidates: list[PlacementCandidate] = []
        required_room_type = str(base_row.get("required_room_type") or "").strip()
        per_slot_limit = max(1, math.ceil(top_k / max(1, len(ranked_slots))))

        for slot_label, slot_score in ranked_slots:
            day, period = _parse_slot_label(slot_label)
            room_model = self.slot_room_models.get(slot_label)
            if room_model is not None:
                stage2_row = dict(base_row)
                stage2_row[SLOT_LABEL] = slot_label
                room_frame = pd.DataFrame([stage2_row], columns=STAGE2_FEATURES)
                room_pool = _catboost_pool(room_frame, STAGE2_CATEGORICAL_FEATURES)
                room_probabilities = room_model.predict_proba(room_pool)[0]
                ranked_rooms = _rank_classes(room_model.classes_, room_probabilities)
                source = "slot_model"
            else:
                ranked_rooms = self._prior_rooms(slot_label, required_room_type)
                source = "room_prior"

            accepted = 0
            for room_name, room_score in ranked_rooms:
                if required_room_type and not self._room_matches(room_name, required_room_type):
                    continue
                score = float(slot_score) * float(room_score)
                candidates.append(
                    PlacementCandidate(
                        resource_key=f"{room_name}|{day}|{period}",
                        classroom_name=str(room_name),
                        day_of_week=day,
                        period_index=period,
                        score=score,
                        slot_score=float(slot_score),
                        room_score=float(room_score),
                        source=source,
                    )
                )
                accepted += 1
                if accepted >= per_slot_limit:
                    break

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_k]

    def _room_matches(self, room_name: str, required_room_type: str) -> bool:
        room = self.room_meta.get(str(room_name), {})
        classroom_type = str(room.get("classroom_type") or "").strip()
        return not classroom_type or classroom_type == required_room_type

    def _prior_rooms(self, slot_label: str, required_room_type: str) -> list[tuple[str, float]]:
        slot_priors = self.room_priors.get("by_slot", {}).get(slot_label, [])
        global_priors = self.room_priors.get("global", [])
        ranked = slot_priors or global_priors
        result = []
        for item in ranked:
            room_name = str(item.get("classroom_name") or "")
            if not room_name:
                continue
            if required_room_type and not self._room_matches(room_name, required_room_type):
                continue
            result.append((room_name, float(item.get("probability") or 0.0)))
        return result


def train(
    data_path: Path = DATA_PATH,
    output_dir: Path = OUTPUT_DIR,
    *,
    min_slot_samples: int = 20,
    iterations: int = 300,
) -> Path:
    CatBoostClassifier = _catboost_classifier()
    if not data_path.exists():
        raise FileNotFoundError(f"Training samples not found: {data_path}")

    df = _load_training_frame(data_path)
    train_idx, test_idx = _group_split(df)
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    stage2_dir = output_dir / "stage2_slots"
    stage2_dir.mkdir(parents=True, exist_ok=True)

    stage1 = CatBoostClassifier(
        loss_function="MultiClass",
        iterations=iterations,
        depth=6,
        learning_rate=0.08,
        random_seed=42,
        auto_class_weights="Balanced",
        verbose=False,
        allow_writing_files=False,
    )
    stage1.fit(
        train_df[STAGE1_FEATURES],
        train_df[SLOT_LABEL],
        cat_features=CATEGORICAL_FEATURES,
        eval_set=(test_df[STAGE1_FEATURES], test_df[SLOT_LABEL]),
        use_best_model=True,
    )
    stage1_model_path = output_dir / "stage1_slot.cbm"
    stage1.save_model(stage1_model_path)

    slot_room_models: dict[str, dict[str, Any]] = {}
    for slot_label, slot_df in train_df.groupby(SLOT_LABEL):
        room_count = slot_df[ROOM_LABEL].nunique()
        if len(slot_df) < min_slot_samples or room_count < 2:
            continue
        model = CatBoostClassifier(
            loss_function="MultiClass",
            iterations=max(80, iterations // 3),
            depth=4,
            learning_rate=0.1,
            random_seed=44,
            auto_class_weights="Balanced",
            verbose=False,
            allow_writing_files=False,
        )
        model.fit(slot_df[STAGE2_FEATURES], slot_df[ROOM_LABEL], cat_features=STAGE2_CATEGORICAL_FEATURES)
        safe_slot = str(slot_label).replace("|", "_")
        model_path = stage2_dir / f"room_{safe_slot}.cbm"
        model.save_model(model_path)
        slot_room_models[str(slot_label)] = {
            "model_path": str(model_path),
            "training_samples": int(len(slot_df)),
            "room_count": int(room_count),
        }

    room_priors = _room_priors(train_df)
    loaded_model = V35PlacementModel(
        stage1=stage1,
        slot_room_models=_load_in_memory_slot_models(stage2_dir, slot_room_models),
        meta={"rooms": _room_meta(df), "room_priors": room_priors},
    )
    metrics = _evaluate(test_df, loaded_model)

    meta = {
        "model_type": "v3.5_catboost_two_stage_placement",
        "version": "0.1",
        "training_data": str(data_path),
        "stage1_model_path": str(stage1_model_path),
        "slot_room_models": slot_room_models,
        "features": {
            "stage1": STAGE1_FEATURES,
            "stage1_categorical": CATEGORICAL_FEATURES,
            "stage2": STAGE2_FEATURES,
            "stage2_categorical": STAGE2_CATEGORICAL_FEATURES,
        },
        "contract": {
            "input": STAGE1_FEATURES,
            "output": ["resource_key", "classroom_name", "day_of_week", "period_index", "score"],
        },
        "training_samples": int(len(df)),
        "source_key_count": int(df["source_key"].nunique()),
        "slot_count": int(df[SLOT_LABEL].nunique()),
        "room_count": int(df[ROOM_LABEL].nunique()),
        "slot_model_count": int(len(slot_room_models)),
        "min_slot_samples": int(min_slot_samples),
        "metrics": metrics,
        "rooms": _room_meta(df),
        "room_priors": room_priors,
    }
    meta_path = output_dir / "placement_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"训练样本: {len(df)}")
    print(f"时段类别: {df[SLOT_LABEL].nunique()}")
    print(f"教室类别: {df[ROOM_LABEL].nunique()}")
    print(f"时段子模型: {len(slot_room_models)}")
    print("评估结果:")
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")
    print(f"模型目录: {output_dir}")
    return meta_path


def predict_sample(meta_dir: Path = OUTPUT_DIR, data_path: Path = DATA_PATH, *, index: int = 0, top_k: int = 20) -> list[dict[str, Any]]:
    df = _load_training_frame(data_path)
    if index < 0 or index >= len(df):
        raise IndexError(f"index out of range: {index}, samples={len(df)}")
    model = V35PlacementModel.load(meta_dir)
    row = df.iloc[index].to_dict()
    candidates = model.predict_topk(row, top_k=top_k)
    return [candidate.to_dict() for candidate in candidates]


def _load_training_frame(data_path: Path) -> pd.DataFrame:
    if data_path.suffix == ".jsonl":
        rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        df = pd.DataFrame(rows)
    else:
        df = pd.read_csv(data_path)
    df.columns = [str(column).strip() for column in df.columns]
    for column in CATEGORICAL_FEATURES + [ROOM_LABEL]:
        df[column] = df.get(column, "").astype(str).fillna("").str.strip()
    for column in NUMERIC_FEATURES + ["day_of_week", "period_index", "classroom_capacity"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    df = df[df[ROOM_LABEL].astype(str).str.strip() != ""].copy()
    df = df[(df["day_of_week"] > 0) & (df["period_index"] > 0)].copy()
    df[SLOT_LABEL] = df["day_of_week"].astype(int).astype(str) + "|" + df["period_index"].astype(int).astype(str)
    return df


def _normalize_task_row(task_like: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    aliases = {
        "class_name": ["class_name", "class_group", "class_group_names"],
        "class_major": ["class_major", "class_group_majors"],
        "class_department": ["class_department", "class_group_departments"],
        "class_grade": ["class_grade", "class_group_grades"],
    }
    for feature in CATEGORICAL_FEATURES:
        keys = aliases.get(feature, [feature])
        row[feature] = str(_first_present(task_like, keys, "")).strip()
    for feature in NUMERIC_FEATURES:
        keys = aliases.get(feature, [feature])
        row[feature] = _safe_float(_first_present(task_like, keys, 0))
    return row


def _first_present(source: dict[str, Any], keys: list[str], default: Any) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def _safe_float(value: Any) -> float:
    if isinstance(value, str) and "," in value:
        value = value.split(",")[0]
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _group_split(df: pd.DataFrame):
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    return next(splitter.split(df, groups=df["source_key"].astype(str)))


def _evaluate(test_df: pd.DataFrame, model: V35PlacementModel) -> dict[str, float]:
    hits = {1: 0, 5: 0, 10: 0, 30: 0}
    slot_hits = {1: 0, 3: 0, 5: 0}
    total = 0
    for _source_key, group in test_df.groupby("source_key", dropna=False):
        truth_resources = set(group[RESOURCE_KEY].astype(str).tolist())
        truth_slots = set(group[SLOT_LABEL].astype(str).tolist())
        task = group.iloc[0].to_dict()
        predictions = model.predict_topk(task, top_k=30, slot_top_k=10)
        predicted_resources = [candidate.resource_key for candidate in predictions]
        predicted_slots = [f"{candidate.day_of_week}|{candidate.period_index}" for candidate in predictions]
        total += 1
        for k in hits:
            if truth_resources & set(predicted_resources[:k]):
                hits[k] += 1
        for k in slot_hits:
            if truth_slots & set(predicted_slots[:k]):
                slot_hits[k] += 1
    denominator = max(1, total)
    metrics = {f"hit@{k}": hits[k] / denominator for k in hits}
    metrics.update({f"slot_hit@{k}": slot_hits[k] / denominator for k in slot_hits})
    return {key: round(float(value), 6) for key, value in metrics.items()}


def _room_meta(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for room_name, group in df.groupby(ROOM_LABEL):
        row = group.iloc[0]
        result[str(room_name)] = {
            "classroom_name": str(room_name),
            "classroom_type": str(row.get("classroom_type") or ""),
            "classroom_capacity": int(_safe_float(row.get("classroom_capacity", 0))),
        }
    return result


def _room_priors(df: pd.DataFrame, *, limit: int = 80) -> dict[str, Any]:
    def ranked(group: pd.DataFrame) -> list[dict[str, Any]]:
        counts = group[ROOM_LABEL].astype(str).value_counts()
        total = max(1, int(counts.sum()))
        return [
            {"classroom_name": room, "probability": count / total, "count": int(count)}
            for room, count in counts.head(limit).items()
        ]

    return {
        "global": ranked(df),
        "by_slot": {str(slot): ranked(group) for slot, group in df.groupby(SLOT_LABEL)},
    }


def _rank_classes(classes: Any, probabilities: Any) -> list[tuple[str, float]]:
    pairs = [(str(label), float(probability)) for label, probability in zip(classes, probabilities)]
    pairs.sort(key=lambda item: item[1], reverse=True)
    return pairs


def _parse_slot_label(slot_label: str) -> tuple[int, int]:
    day, period = str(slot_label).split("|")
    return int(day), int(period)


def _load_in_memory_slot_models(stage2_dir: Path, slot_models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    CatBoostClassifier = _catboost_classifier()
    loaded = {}
    for slot_label, info in slot_models.items():
        model = CatBoostClassifier()
        model.load_model(info["model_path"])
        loaded[slot_label] = model
    return loaded


def _catboost_classifier():
    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:
        raise RuntimeError("CatBoost is required for V3.5 placement. Install it with: python -m pip install catboost") from exc
    return CatBoostClassifier


def _catboost_pool(frame: pd.DataFrame, cat_features: list[str]):
    try:
        from catboost import Pool
    except ImportError as exc:
        raise RuntimeError("CatBoost is required for V3.5 placement. Install it with: python -m pip install catboost") from exc
    return Pool(frame, cat_features=cat_features)


def main() -> None:
    parser = argparse.ArgumentParser(description="V3.5 two-stage placement model")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--data", default=str(DATA_PATH))
    train_parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    train_parser.add_argument("--min-slot-samples", type=int, default=20)
    train_parser.add_argument("--iterations", type=int, default=300)

    predict_parser = subparsers.add_parser("predict-sample")
    predict_parser.add_argument("--data", default=str(DATA_PATH))
    predict_parser.add_argument("--model-dir", default=str(OUTPUT_DIR))
    predict_parser.add_argument("--index", type=int, default=0)
    predict_parser.add_argument("--top-k", type=int, default=20)

    args = parser.parse_args()
    if args.command == "train":
        train(
            data_path=Path(args.data),
            output_dir=Path(args.output_dir),
            min_slot_samples=args.min_slot_samples,
            iterations=args.iterations,
        )
    elif args.command == "predict-sample":
        predictions = predict_sample(Path(args.model_dir), Path(args.data), index=args.index, top_k=args.top_k)
        print(json.dumps(predictions, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
