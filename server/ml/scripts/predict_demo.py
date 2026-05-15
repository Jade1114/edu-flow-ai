"""Run a local prediction demo with the trained schedule scoring model.

Planned input:
    ../models/schedule_ranker_v1.txt
    ../data/feature_schema.json
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}. Run train_lightgbm.py first."
        )
    if not FEATURE_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Feature schema not found: {FEATURE_SCHEMA_PATH}. Run train_lightgbm.py first."
        )
    raise NotImplementedError(
        "Prediction demo is not implemented yet. "
        "Next step: load the model and score sample candidate rows."
    )


if __name__ == "__main__":
    main()
