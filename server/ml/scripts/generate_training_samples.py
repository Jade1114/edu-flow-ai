"""Generate LightGBM training samples for Edu-Flow-AI scheduling.

Planned output:
    ../data/training_samples.csv

A single row represents:
    TeachingTask + candidate TimeSlot + candidate Classroom + current schedule state -> score
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_PATH = DATA_DIR / "training_samples.csv"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raise NotImplementedError(
        "Training sample generation is not implemented yet. "
        "Next step: load project seed/database data and emit training_samples.csv."
    )


if __name__ == "__main__":
    main()
