"""Evaluate generated scheduling scheme demos.

Inputs:
    ../data/generated_scheme_demo.csv
    or ../data/generated/*.csv

The script evaluates scheme-level quality, not single-fragment prediction quality.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEME_PATH = ROOT_DIR / "data" / "generated_scheme_demo.csv"
SCHEME_DIR = ROOT_DIR / "data" / "generated"
RANKED_SUMMARY_PATH = SCHEME_DIR / "ranked_summary.csv"
LOG_PREFIX = "[SCHEDULE-EVAL]"

RANKED_SUMMARY_COLUMNS = [
    "rank",
    "scheme_file",
    "scheme_score",
    "fragment_count",
    "task_count",
    "hard_conflict_count",
    "hard_conflict_rate",
    "early_period_count",
    "late_period_count",
    "avg_predicted_score",
    "avg_rule_score",
    "avg_capacity_ratio",
    "teacher_day_load_max",
    "class_day_load_max",
    "room_day_load_max",
    "teacher_day_load_std",
    "class_day_load_std",
    "room_day_load_std",
    "teacher_week_load_max",
    "class_week_load_max",
    "room_week_load_max",
    "teacher_satisfaction",
    "teacher_unavailable_hit_count",
    "teacher_overload_count",
    "teacher_profile_penalty_total",
    "teacher_profile_penalty_hit_count",
    "weekday_distribution",
    "period_distribution",
    "top_rooms",
]


@dataclass(frozen=True)
class SchemeMetrics:
    fragment_count: int
    task_count: int
    hard_conflict_count: int
    hard_conflict_rate: float
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
    teacher_satisfaction: float
    teacher_unavailable_hit_count: int
    teacher_overload_count: int
    teacher_profile_penalty_total: float
    teacher_profile_penalty_hit_count: int
    scheme_score: float


@dataclass(frozen=True)
class SchemeDistribution:
    weekday_distribution: dict[int, int]
    period_distribution: dict[int, int]
    top_rooms: dict[str, int]


def log_eval(message: str, payload: Any | None = None) -> None:
    if payload is None:
        print(f"{LOG_PREFIX} {message}", flush=True)
        return
    print(f"{LOG_PREFIX} {message}: {json.dumps(payload, ensure_ascii=False, default=str)}", flush=True)


def load_scheme(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Generated scheme not found: {path}. Run generate_scheme_ga.py first.")
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


def build_distribution(rows: list[dict[str, Any]]) -> SchemeDistribution:
    by_day = Counter(as_int(row, "day_of_week") for row in rows)
    by_period = Counter(as_int(row, "period_index") for row in rows)
    by_room = Counter(row["classroom_id"] for row in rows)
    return SchemeDistribution(
        weekday_distribution=dict(sorted(by_day.items())),
        period_distribution=dict(sorted(by_period.items())),
        top_rooms=dict(by_room.most_common(8)),
    )


def load_teacher_penalties(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        log_eval("教师画像惩罚未传入，满意度按满分处理", {"path": str(path) if path else None})
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_penalties = payload.get("teacher_penalties", payload)
    if not isinstance(raw_penalties, dict):
        log_eval("教师画像惩罚 JSON 格式无效，满意度按满分处理", {"path": str(path)})
        return {}
    penalties = {str(key): value for key, value in raw_penalties.items() if isinstance(value, dict)}
    log_eval("教师画像惩罚加载完成", {
        "path": str(path),
        "teacher_count": len(penalties),
        "teachers": [
            {
                "teacher_id": key,
                "unavailable_slots": value.get("unavailable_slots") or [],
                "max_weekly_hours": value.get("max_weekly_hours"),
                "penalty_weight": value.get("penalty_weight"),
                "reason": value.get("reason"),
            }
            for key, value in sorted(penalties.items())
        ],
    })
    return penalties


def normalized_slots(raw_slots: Any) -> set[tuple[int, int]]:
    slots: set[tuple[int, int]] = set()
    if not raw_slots:
        return slots
    for slot in raw_slots:
        if isinstance(slot, (list, tuple)) and len(slot) >= 2:
            try:
                slots.add((int(slot[0]), int(slot[1])))
            except (TypeError, ValueError):
                continue
    return slots


def compute_teacher_satisfaction(
    rows: list[dict[str, Any]],
    penalties: dict[str, dict[str, Any]],
    teacher_week_load: Counter[tuple[str, int]],
) -> tuple[float, int, int]:
    if not rows or not penalties:
        return 100.0, 0, 0
    unavailable_hit_count = 0
    for row in rows:
        teacher_id = str(row.get("teacher_id") or row.get("teaching_task_id"))
        penalty = penalties.get(teacher_id)
        if not penalty:
            continue
        if (as_int(row, "day_of_week"), as_int(row, "period_index")) in normalized_slots(penalty.get("unavailable_slots")):
            unavailable_hit_count += 1

    overloaded_teachers: set[str] = set()
    for (teacher_id, _week_number), load in teacher_week_load.items():
        penalty = penalties.get(str(teacher_id))
        if not penalty or penalty.get("max_weekly_hours") is None:
            continue
        try:
            max_weekly_hours = int(penalty["max_weekly_hours"])
        except (TypeError, ValueError):
            continue
        if load > max_weekly_hours:
            overloaded_teachers.add(str(teacher_id))

    hit_rate = unavailable_hit_count / len(rows)
    overload_rate = len(overloaded_teachers) / max(len(penalties), 1)
    satisfaction = max(0.0, min(100.0, 100.0 - hit_rate * 70.0 - overload_rate * 30.0))
    return round(satisfaction, 2), unavailable_hit_count, len(overloaded_teachers)


def evaluate_scheme(rows: list[dict[str, Any]], teacher_penalties: dict[str, dict[str, Any]] | None = None) -> SchemeMetrics:
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
        teacher_id = row.get("teacher_id") or task_id
        room_id = row["classroom_id"]
        week_number = as_int(row, "week_number")
        day_of_week = as_int(row, "day_of_week")

        teacher_key = (teacher_id, week_number, day_of_week)
        class_key = (task_id, week_number, day_of_week)
        room_key = (room_id, week_number, day_of_week)
        teacher_week_key = (teacher_id, week_number)
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
    teacher_profile_penalties = [as_float(row, "teacher_profile_penalty") for row in rows]
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

    hard_conflict_rate = len(hard_conflicts) / len(rows)
    hard_conflict_penalty = min(35.0, hard_conflict_rate * 45.0 + len(hard_conflicts) * 1.5)
    early_late_penalty = (early_period_count + late_period_count) * 0.05
    teacher_balance_penalty = stdev_or_zero(teacher_day_values) * 1.2
    class_balance_penalty = stdev_or_zero(class_day_values) * 1.2
    room_balance_penalty = stdev_or_zero(room_day_values) * 0.8
    teacher_satisfaction, unavailable_hit_count, overload_count = compute_teacher_satisfaction(
        rows,
        teacher_penalties or {},
        teacher_week_load,
    )
    teacher_profile_penalty_total = sum(teacher_profile_penalties)
    teacher_profile_penalty_hit_count = sum(1 for value in teacher_profile_penalties if value > 0)

    avg_predicted_score = sum(predicted_scores) / len(predicted_scores)
    avg_rule_score = sum(rule_scores) / len(rule_scores)
    base_score = 100 * ((avg_predicted_score + avg_rule_score) / 2)
    teacher_satisfaction_penalty = (100.0 - teacher_satisfaction) * 0.25
    log_eval("方案评分机制拆解", {
        "formula": "scheme_score = clamp(base_score - hard_conflict_penalty - early_late_penalty - teacher_balance_penalty - class_balance_penalty - room_balance_penalty - teacher_satisfaction_penalty, 0, 100)",
        "base_score_formula": "100 * ((avg_predicted_score + avg_rule_score) / 2)",
        "hard_conflict_penalty_formula": "min(35, hard_conflict_rate*45 + hard_conflict_count*1.5)",
        "base_score": round(base_score, 6),
        "avg_predicted_score": round(avg_predicted_score, 6),
        "avg_rule_score": round(avg_rule_score, 6),
        "hard_conflict_count": len(hard_conflicts),
        "hard_conflict_rate": round(hard_conflict_rate, 6),
        "hard_conflict_penalty": round(hard_conflict_penalty, 6),
        "early_late_penalty": round(early_late_penalty, 6),
        "teacher_balance_penalty": round(teacher_balance_penalty, 6),
        "class_balance_penalty": round(class_balance_penalty, 6),
        "room_balance_penalty": round(room_balance_penalty, 6),
        "teacher_satisfaction": teacher_satisfaction,
        "teacher_satisfaction_penalty": round(teacher_satisfaction_penalty, 6),
        "teacher_unavailable_hit_count": unavailable_hit_count,
        "teacher_overload_count": overload_count,
        "teacher_profile_penalty_total": round(teacher_profile_penalty_total, 6),
        "teacher_profile_penalty_hit_count": teacher_profile_penalty_hit_count,
    })
    scheme_score = max(
        0.0,
        min(
            100.0,
            base_score
            - hard_conflict_penalty
            - early_late_penalty
            - teacher_balance_penalty
            - class_balance_penalty
            - room_balance_penalty
            - teacher_satisfaction_penalty,
        ),
    )

    return SchemeMetrics(
        fragment_count=len(rows),
        task_count=len({row["teaching_task_id"] for row in rows}),
        hard_conflict_count=len(hard_conflicts),
        hard_conflict_rate=hard_conflict_rate,
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
        teacher_satisfaction=teacher_satisfaction,
        teacher_unavailable_hit_count=unavailable_hit_count,
        teacher_overload_count=overload_count,
        teacher_profile_penalty_total=teacher_profile_penalty_total,
        teacher_profile_penalty_hit_count=teacher_profile_penalty_hit_count,
        scheme_score=scheme_score,
    )


def print_metrics(metrics: SchemeMetrics) -> None:
    print("## Scheme Quality Metrics")
    print(f"Fragments              : {metrics.fragment_count}")
    print(f"Teaching tasks         : {metrics.task_count}")
    print(f"Hard-conflict fragments: {metrics.hard_conflict_count}")
    print(f"Hard-conflict rate     : {metrics.hard_conflict_rate:.2%}")
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
    print(f"Teacher satisfaction   : {metrics.teacher_satisfaction:.2f}/100")
    print(f"Teacher unavailable hit: {metrics.teacher_unavailable_hit_count}")
    print(f"Teacher overload count : {metrics.teacher_overload_count}")
    print(f"Teacher profile penalty: {metrics.teacher_profile_penalty_total:.2f}")
    print(f"Profile penalty hits   : {metrics.teacher_profile_penalty_hit_count}")
    print(f"Scheme score           : {metrics.scheme_score:.2f}/100")


def print_distribution(distribution: SchemeDistribution) -> None:
    print("\n## Distribution")
    print("Fragments by weekday:", distribution.weekday_distribution)
    print("Fragments by period :", distribution.period_distribution)
    print("Top rooms           :", distribution.top_rooms)


def scheme_summary_row(rank: int, scheme_file: Path, metrics: SchemeMetrics, distribution: SchemeDistribution) -> dict[str, Any]:
    metrics_dict = asdict(metrics)
    return {
        "rank": rank,
        "scheme_file": scheme_file.name,
        **{key: round(value, 6) if isinstance(value, float) else value for key, value in metrics_dict.items()},
        "weekday_distribution": json.dumps(distribution.weekday_distribution, ensure_ascii=False),
        "period_distribution": json.dumps(distribution.period_distribution, ensure_ascii=False),
        "top_rooms": json.dumps(distribution.top_rooms, ensure_ascii=False),
    }


def write_ranked_summary(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RANKED_SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)



def compute_dimensional_scores(metrics: SchemeMetrics, distribution: SchemeDistribution) -> dict[str, float]:
    used_days = sum(1 for count in distribution.weekday_distribution.values() if count > 0)
    used_rooms = len(distribution.top_rooms)

    teacher_score = max(0.0, min(100.0,
        100.0
        - metrics.teacher_day_load_std * 30
        - metrics.teacher_week_load_max * 2.5
        - metrics.early_period_count * 0.8
        - metrics.late_period_count * 1.2
    ))

    class_balance_score = max(0.0, min(100.0,
        100.0
        - metrics.class_day_load_std * 30
        - metrics.class_week_load_max * 2.5
    ))

    room_util_score = max(0.0, min(100.0,
        100.0
        - metrics.room_day_load_std * 25
        - max(0.0, (metrics.fragment_count / max(used_rooms, 1) - 20) * 0.5)
    ))

    compact_score = max(0.0, min(100.0,
        (7 - used_days) * 14.28
        + min(1.0, metrics.fragment_count / max(used_days, 1) / 80) * 20
    ))

    return {
        "teacher_score": round(teacher_score, 2),
        "class_balance_score": round(class_balance_score, 2),
        "room_util_score": round(room_util_score, 2),
        "compact_score": round(compact_score, 2),
    }


def evaluate_scheme_to_dict(
    rows: list[dict[str, Any]],
    scheme_file: Path,
    teacher_penalties: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metrics = evaluate_scheme(rows, teacher_penalties)
    distribution = build_distribution(rows)
    dimensions = compute_dimensional_scores(metrics, distribution)
    metrics_dict = asdict(metrics)
    return {
        "scheme_file": scheme_file.name,
        **{key: round(value, 6) if isinstance(value, float) else value for key, value in metrics_dict.items()},
        **dimensions,
        "weekday_distribution": {str(day): count for day, count in distribution.weekday_distribution.items()},
        "period_distribution": {str(period): count for period, count in distribution.period_distribution.items()},
        "top_rooms": distribution.top_rooms,
    }


def write_evaluation_json(evaluation: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate_single_csv_to_json(scheme_path: Path, teacher_penalties: dict[str, dict[str, Any]] | None = None) -> Path:
    log_eval("开始评估方案 CSV", {"scheme_file": str(scheme_path)})
    rows = load_scheme(scheme_path)
    evaluation = evaluate_scheme_to_dict(rows, scheme_path, teacher_penalties)
    log_eval("方案评估结果", evaluation)
    json_path = scheme_path.with_suffix(".json")
    write_evaluation_json(evaluation, json_path)
    print(f"Evaluation JSON → {json_path}")
    return json_path


def evaluate_directory_to_json(scheme_dir: Path, teacher_penalties: dict[str, dict[str, Any]] | None = None) -> list[Path]:
    schemes_jsonl = scheme_dir / "schemes.jsonl"
    if schemes_jsonl.exists():
        return _evaluate_schemes_jsonl(schemes_jsonl, teacher_penalties)
    scheme_files = sorted(path for path in scheme_dir.glob("scheme_*.csv") if path.is_file())
    if not scheme_files:
        raise FileNotFoundError(f"No scheme_*.csv or schemes.jsonl found in {scheme_dir}")
    json_paths: list[Path] = []
    for scheme_file in scheme_files:
        json_paths.append(evaluate_single_csv_to_json(scheme_file, teacher_penalties))
    return json_paths


def _evaluate_schemes_jsonl(schemes_jsonl: Path, teacher_penalties: dict[str, dict[str, Any]] | None = None) -> list[Path]:
    """Evaluate all schemes from a schemes.jsonl file and write evaluation JSONs."""
    json_paths: list[Path] = []
    for i, line in enumerate(schemes_jsonl.read_text(encoding="utf-8").strip().split("\n")):
        if not line.strip():
            continue
        scheme_entry = json.loads(line)
        rows = scheme_entry.get("items", [])
        if not rows:
            continue
        scheme_no = i + 1
        scheme_path = schemes_jsonl.parent / f"scheme_{scheme_no:03d}.csv"
        evaluation = evaluate_scheme_to_dict(rows, scheme_path, teacher_penalties)
        json_path = schemes_jsonl.parent / f"scheme_{scheme_no:03d}.json"
        write_evaluation_json(evaluation, json_path)
        print(f"Evaluation JSON → {json_path}")
        json_paths.append(json_path)
    if not json_paths:
        raise ValueError(f"No valid schemes found in {schemes_json}")
    return json_paths


def evaluate_scheme_directory(
    scheme_dir: Path,
    output_path: Path,
    teacher_penalties: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not scheme_dir.exists():
        raise FileNotFoundError(f"Scheme directory not found: {scheme_dir}. Run generate_scheme_ga.py first.")
    scheme_files = sorted(path for path in scheme_dir.glob("scheme_*.csv") if path.is_file())
    if not scheme_files:
        raise FileNotFoundError(f"No scheme_*.csv files found in {scheme_dir}")

    evaluated: list[tuple[Path, SchemeMetrics, SchemeDistribution]] = []
    for scheme_file in scheme_files:
        rows = load_scheme(scheme_file)
        evaluated.append((scheme_file, evaluate_scheme(rows, teacher_penalties), build_distribution(rows)))

    evaluated.sort(key=lambda item: item[1].scheme_score, reverse=True)
    summary_rows = [
        scheme_summary_row(rank, scheme_file, metrics, distribution)
        for rank, (scheme_file, metrics, distribution) in enumerate(evaluated, start=1)
    ]
    write_ranked_summary(summary_rows, output_path)
    return summary_rows


def print_ranked_summary(summary_rows: list[dict[str, Any]], top: int) -> None:
    print("## Ranked Scheme Summary")
    for row in summary_rows[:top]:
        print(
            f"#{row['rank']} {row['scheme_file']} "
            f"score={row['scheme_score']:.2f} "
            f"conflicts={row['hard_conflict_count']} "
            f"early={row['early_period_count']} late={row['late_period_count']} "
            f"room_std={row['room_day_load_std']:.4f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated scheduling scheme demos.")
    parser.add_argument("--scheme", type=Path, default=SCHEME_PATH, help="Generated scheme CSV path.")
    parser.add_argument("--scheme-dir", type=Path, default=None, help="Directory containing scheme_*.csv files.")
    parser.add_argument("--output", type=Path, default=None, help="Output path for ranked summary CSV in directory mode.")
    parser.add_argument("--top", type=int, default=10, help="Number of ranked schemes to print in directory mode.")
    parser.add_argument("--teacher-penalties", type=Path, default=None, help="Teacher penalty JSON prepared by Java and copied by the scheme generator.")
    parser.add_argument("--json", action="store_true", help="Output evaluation JSON files next to each scheme CSV.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    teacher_penalties = load_teacher_penalties(args.teacher_penalties)
    if args.json:
        if args.scheme_dir is not None:
            json_paths = evaluate_directory_to_json(args.scheme_dir, teacher_penalties)
            print(f"Generated {len(json_paths)} evaluation JSON files in {args.scheme_dir}")
            return
        json_path = evaluate_single_csv_to_json(args.scheme, teacher_penalties)
        print(f"Generated evaluation JSON → {json_path}")
        return

    if args.scheme_dir is not None:
        output_path = args.output or (args.scheme_dir / "ranked_summary.csv")
        summary_rows = evaluate_scheme_directory(args.scheme_dir, output_path, teacher_penalties)
        print_ranked_summary(summary_rows, args.top)
        print(f"\nRanked summary -> {output_path}")
        return

    rows = load_scheme(args.scheme)
    metrics = evaluate_scheme(rows, teacher_penalties)
    distribution = build_distribution(rows)
    print_metrics(metrics)
    print_distribution(distribution)


if __name__ == "__main__":
    main()
