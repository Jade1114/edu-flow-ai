"""Train the first LightGBM schedule scoring model.

Planned input:
    ../data/training_samples.csv

Planned outputs:
    ../models/schedule_ranker_v1.txt
    ../data/feature_schema.json
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "training_samples.csv"
MODEL_PATH = ROOT_DIR / "models" / "schedule_ranker_v1.txt"
FEATURE_SCHEMA_PATH = ROOT_DIR / "data" / "feature_schema.json"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Training samples not found: {DATA_PATH}. "
            "Run generate_training_samples.py first."
        )
    raise NotImplementedError(
        "LightGBM training is not implemented yet. "
        "Next step: read training_samples.csv, train a regressor, and save the model."
    )


if __name__ == "__main__":
    main()
