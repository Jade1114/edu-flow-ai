"""Evaluate a generated scheduling scheme demo.

Input:
    ../data/generated_scheme_demo.csv

The script evaluates scheme-level quality, not single-fragment prediction quality.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEME_PATH = ROOT_DIR / "data" / "generated_scheme_demo.csv"


@dataclass(frozen=True)
class SchemeMetrics:
    fragment_count: int
    task_count: int
    hard_conflict_count: int
    early_period_count: int
    late_period_count: int
    avg_predicted_score: float
    avg_rule_score: float
    avg_capacity_ratio: float | None
    teacher_day_load_max: int
    class_day_load_max: int
    room_day_load_max: int
    teacher_day_load_std: float
    class_day_load_std: float
    room_day_load_std: float
    teacher_week_load_max: int
    class_week_load_max: int
    room_week_load_max: int
    scheme_score: float


def load_scheme(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Generated scheme not found: {path}. Run generate_scheme_demo.py first.")
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError(f"Generated scheme is empty: {path}")
    return rows


def as_int(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key)
    if value in (None, ""):
        return default
    return int(float(value))


def as_float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    if value in (None, ""):
        return default
    return float(value)


def stdev_or_zero(values: list[int]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(statistics.pstdev(values))


def evaluate_scheme(rows: list[dict[str, Any]]) -> SchemeMetrics:
    teacher_day_load: Counter[tuple[str, int, int]] = Counter()
    class_day_load: Counter[tuple[str, int, int]] = Counter()
    room_day_load: Counter[tuple[str, int, int]] = Counter()
    teacher_week_load: Counter[tuple[str, int]] = Counter()
    class_week_load: Counter[tuple[str, int]] = Counter()
    room_week_load: Counter[tuple[str, int]] = Counter()

    # The generated demo currently does not include teacher/class IDs. Use teaching_task_id as a
    # stable proxy for class/course distribution until the demo output is expanded.
    for row in rows:
        task_id = row["teaching_task_id"]
        room_id = row["classroom_id"]
        week_number = as_int(row, "week_number")
        day_of_week = as_int(row, "day_of_week")

        teacher_key = (task_id, week_number, day_of_week)
        class_key = (task_id, week_number, day_of_week)
        room_key = (room_id, week_number, day_of_week)
        teacher_week_key = (task_id, week_number)
        class_week_key = (task_id, week_number)
        room_week_key = (room_id, week_number)

        teacher_day_load[teacher_key] += 1
        class_day_load[class_key] += 1
        room_day_load[room_key] += 1
        teacher_week_load[teacher_week_key] += 1
        class_week_load[class_week_key] += 1
        room_week_load[room_week_key] += 1

    predicted_scores = [as_float(row, "predicted_score") for row in rows]
    rule_scores = [as_float(row, "rule_score") for row in rows]
    hard_conflicts = [row for row in rows if as_int(row, "has_hard_conflict") == 1]
    early_period_count = sum(1 for row in rows if as_int(row, "period_index") == 1)
    late_period_count = sum(1 for row in rows if as_int(row, "period_index") >= 5)

    capacity_ratios = [as_float(row, "capacity_ratio") for row in rows if row.get("capacity_ratio") not in (None, "")]
    avg_capacity_ratio = sum(capacity_ratios) / len(capacity_ratios) if capacity_ratios else None

    teacher_day_values = list(teacher_day_load.values())
    class_day_values = list(class_day_load.values())
    room_day_values = list(room_day_load.values())
    teacher_week_values = list(teacher_week_load.values())
    class_week_values = list(class_week_load.values())
    room_week_values = list(room_week_load.values())

    hard_conflict_penalty = len(hard_conflicts) * 12
    early_late_penalty = (early_period_count + late_period_count) * 0.05
    teacher_balance_penalty = stdev_or_zero(teacher_day_values) * 1.2
    class_balance_penalty = stdev_or_zero(class_day_values) * 1.2
    room_balance_penalty = stdev_or_zero(room_day_values) * 0.8

    avg_predicted_score = sum(predicted_scores) / len(predicted_scores)
    avg_rule_score = sum(rule_scores) / len(rule_scores)
    base_score = 100 * ((avg_predicted_score + avg_rule_score) / 2)
    scheme_score = max(
        0.0,
        min(
            100.0,
            base_score
            - hard_conflict_penalty
            - early_late_penalty
            - teacher_balance_penalty
            - class_balance_penalty
            - room_balance_penalty,
        ),
    )

    return SchemeMetrics(
        fragment_count=len(rows),
        task_count=len({row["teaching_task_id"] for row in rows}),
        hard_conflict_count=len(hard_conflicts),
        early_period_count=early_period_count,
        late_period_count=late_period_count,
        avg_predicted_score=avg_predicted_score,
        avg_rule_score=avg_rule_score,
        avg_capacity_ratio=avg_capacity_ratio,
        teacher_day_load_max=max(teacher_day_values or [0]),
        class_day_load_max=max(class_day_values or [0]),
        room_day_load_max=max(room_day_values or [0]),
        teacher_day_load_std=stdev_or_zero(teacher_day_values),
        class_day_load_std=stdev_or_zero(class_day_values),
        room_day_load_std=stdev_or_zero(room_day_values),
        teacher_week_load_max=max(teacher_week_values or [0]),
        class_week_load_max=max(class_week_values or [0]),
        room_week_load_max=max(room_week_values or [0]),
        scheme_score=scheme_score,
    )


def print_metrics(metrics: SchemeMetrics) -> None:
    print("## Scheme Quality Metrics")
    print(f"Fragments              : {metrics.fragment_count}")
    print(f"Teaching tasks         : {metrics.task_count}")
    print(f"Hard-conflict fragments: {metrics.hard_conflict_count}")
    print(f"Early-period fragments : {metrics.early_period_count}")
    print(f"Late-period fragments  : {metrics.late_period_count}")
    print(f"Avg predicted score    : {metrics.avg_predicted_score:.4f}")
    print(f"Avg rule score         : {metrics.avg_rule_score:.4f}")
    if metrics.avg_capacity_ratio is not None:
        print(f"Avg capacity ratio     : {metrics.avg_capacity_ratio:.4f}")
    print(f"Teacher day max load   : {metrics.teacher_day_load_max}")
    print(f"Class day max load     : {metrics.class_day_load_max}")
    print(f"Room day max load      : {metrics.room_day_load_max}")
    print(f"Teacher day load std   : {metrics.teacher_day_load_std:.4f}")
    print(f"Class day load std     : {metrics.class_day_load_std:.4f}")
    print(f"Room day load std      : {metrics.room_day_load_std:.4f}")
    print(f"Teacher week max load  : {metrics.teacher_week_load_max}")
    print(f"Class week max load    : {metrics.class_week_load_max}")
    print(f"Room week max load     : {metrics.room_week_load_max}")
    print(f"Scheme score           : {metrics.scheme_score:.2f}/100")


def print_distribution(rows: list[dict[str, Any]]) -> None:
    by_day = Counter(as_int(row, "day_of_week") for row in rows)
    by_period = Counter(as_int(row, "period_index") for row in rows)
    by_room = Counter(row["classroom_id"] for row in rows)

    print("\n## Distribution")
    print("Fragments by weekday:", dict(sorted(by_day.items())))
    print("Fragments by period :", dict(sorted(by_period.items())))
    print("Top rooms           :", dict(by_room.most_common(8)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a generated scheduling scheme demo.")
    parser.add_argument("--scheme", type=Path, default=SCHEME_PATH, help="Generated scheme CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_scheme(args.scheme)
    metrics = evaluate_scheme(rows)
    print_metrics(metrics)
    print_distribution(rows)


if __name__ == "__main__":
    main()
