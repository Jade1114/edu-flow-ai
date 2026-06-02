"""Analyze V3 task plan quality before global GA selection.

The report focuses on whether local task plans are diverse enough for the GA to
resolve global conflicts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.scheduling_v3.global_plan_selector import _evaluate, load_task_plans

DEFAULT_TOP_N = 20


def analyze_task_plans(
    task_plans_path: str | Path,
    *,
    scheme_path: str | Path | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    source_path = Path(task_plans_path)
    tasks = load_task_plans(source_path)
    if not tasks:
        raise ValueError(f"no task plans found: {source_path}")

    top_n = max(1, int(top_n))
    baseline = _evaluate(tuple(0 for _ in tasks), tasks)
    plan_counts = [len(task.options) for task in tasks]
    total_options = sum(plan_counts)
    total_sessions = sum(len(option.assignments) for task in tasks for option in task.options)

    slot_assignment_counts: Counter[tuple[int, int]] = Counter()
    slot_task_counts: Counter[tuple[int, int]] = Counter()
    room_assignment_counts: Counter[tuple[int, str]] = Counter()
    room_task_counts: Counter[tuple[int, str]] = Counter()
    resource_assignment_counts: Counter[tuple[int, int, int, str]] = Counter()
    resource_task_counts: Counter[tuple[int, int, int, str]] = Counter()
    signature_counts: Counter[str] = Counter()
    low_diversity_tasks: list[dict[str, Any]] = []

    for task in tasks:
        task_slots: set[tuple[int, int]] = set()
        task_rooms: set[tuple[int, str]] = set()
        task_resources: set[tuple[int, int, int, str]] = set()
        task_signatures: set[str] = set()
        for option in task.options:
            option_slots: set[tuple[int, int]] = set()
            option_rooms: set[tuple[int, str]] = set()
            option_resources: set[tuple[int, int, int, str]] = set()
            for assignment in option.assignments:
                slot_key = (int(assignment.get("day_of_week") or 0), int(assignment.get("period_index") or 0))
                room_key = (
                    int(assignment.get("classroom_id") or 0),
                    str(assignment.get("classroom_name") or ""),
                )
                resource_key = (*slot_key, room_key[0], room_key[1])
                slot_assignment_counts[slot_key] += 1
                room_assignment_counts[room_key] += 1
                resource_assignment_counts[resource_key] += 1
                option_slots.add(slot_key)
                option_rooms.add(room_key)
                option_resources.add(resource_key)
            task_slots.update(option_slots)
            task_rooms.update(option_rooms)
            task_resources.update(option_resources)
            task_signatures.add(_option_signature(option))
        for slot in task_slots:
            slot_task_counts[slot] += 1
        for room in task_rooms:
            room_task_counts[room] += 1
        for resource in task_resources:
            resource_task_counts[resource] += 1
        for signature in task_signatures:
            signature_counts[signature] += 1
        if len(task_signatures) <= 1 or len(task_slots) <= 2 or len(task_rooms) <= 1:
            low_diversity_tasks.append(_low_diversity_row(task, task_signatures, task_slots, task_rooms, task_resources))

    report = {
        "source_path": str(source_path),
        "task_count": len(tasks),
        "total_plan_options": total_options,
        "avg_plans_per_task": round(total_options / max(1, len(tasks)), 3),
        "min_plans_per_task": min(plan_counts),
        "max_plans_per_task": max(plan_counts),
        "total_option_sessions": total_sessions,
        "baseline_plan_1": {
            "hard_conflicts": baseline.fitness.hard_conflicts,
            "quality_score": baseline.fitness.quality_score,
            "beauty_penalty": baseline.fitness.beauty_penalty,
            "conflict_summary": baseline.fitness.conflict_summary,
            "assignment_count": baseline.fitness.assignment_count,
        },
        "diversity": {
            "low_diversity_task_count": len(low_diversity_tasks),
            "low_diversity_task_rate": round(len(low_diversity_tasks) / max(1, len(tasks)), 4),
            "sample_low_diversity_tasks": low_diversity_tasks[:top_n],
            "unique_plan_signatures": len(signature_counts),
            "reused_plan_signature_count": sum(1 for count in signature_counts.values() if count > 1),
        },
        "hotspots": {
            "top_slots_by_assignment_count": _top_pairs(slot_assignment_counts, top_n, _format_slot),
            "top_slots_by_task_count": _top_pairs(slot_task_counts, top_n, _format_slot),
            "top_rooms_by_assignment_count": _top_pairs(room_assignment_counts, top_n, _format_room),
            "top_rooms_by_task_count": _top_pairs(room_task_counts, top_n, _format_room),
            "top_resources_by_assignment_count": _top_pairs(resource_assignment_counts, top_n, _format_resource),
            "top_resources_by_task_count": _top_pairs(resource_task_counts, top_n, _format_resource),
        },
    }

    if scheme_path:
        report["scheme_comparison"] = _scheme_comparison(Path(scheme_path), baseline.fitness.hard_conflicts)
    else:
        default_scheme_path = source_path.parent / "schemes.jsonl"
        if default_scheme_path.exists():
            report["scheme_comparison"] = _scheme_comparison(default_scheme_path, baseline.fitness.hard_conflicts)
    return report


def _option_signature(option: Any) -> str:
    rows = []
    for assignment in option.assignments:
        rows.append((
            int(assignment.get("week_number") or 0),
            int(assignment.get("day_of_week") or 0),
            int(assignment.get("period_index") or 0),
            int(assignment.get("classroom_id") or 0),
        ))
    return json.dumps(sorted(rows), separators=(",", ":"))


def _low_diversity_row(
    task: Any,
    signatures: set[str],
    slots: set[tuple[int, int]],
    rooms: set[tuple[int, str]],
    resources: set[tuple[int, int, int, str]],
) -> dict[str, Any]:
    row = task.row
    input_data = row.get("input") or {}
    return {
        "teaching_task_id": row.get("teaching_task_id"),
        "course_name": input_data.get("course_name"),
        "teacher_name": input_data.get("teacher_name"),
        "class_name": input_data.get("class_name"),
        "plan_count": len(task.options),
        "distinct_plan_signatures": len(signatures),
        "distinct_slots": len(slots),
        "distinct_classrooms": len(rooms),
        "distinct_resources": len(resources),
    }


def _scheme_comparison(path: Path, baseline_conflicts: int) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"scheme file not found: {path}")
    schemes = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            hard = int(row.get("hard_conflicts") or 0)
            schemes.append({
                "scheme_index": row.get("scheme_index"),
                "hard_conflicts": hard,
                "conflict_summary": row.get("conflict_summary") or {},
                "improvement_vs_plan_1": baseline_conflicts - hard,
            })
    return {
        "scheme_path": str(path),
        "scheme_count": len(schemes),
        "schemes": schemes,
    }


def _top_pairs(counter: Counter, top_n: int, formatter) -> list[dict[str, Any]]:
    return [
        {**formatter(key), "count": count}
        for key, count in counter.most_common(top_n)
    ]


def _format_slot(key: tuple[int, int]) -> dict[str, Any]:
    day, period = key
    return {"day_of_week": day, "period_index": period}


def _format_room(key: tuple[int, str]) -> dict[str, Any]:
    room_id, room_name = key
    return {"classroom_id": room_id, "classroom_name": room_name}


def _format_resource(key: tuple[int, int, int, str]) -> dict[str, Any]:
    day, period, room_id, room_name = key
    return {
        "day_of_week": day,
        "period_index": period,
        "classroom_id": room_id,
        "classroom_name": room_name,
    }


def _print_report(report: dict[str, Any]) -> None:
    baseline = report["baseline_plan_1"]
    diversity = report["diversity"]
    hotspots = report["hotspots"]
    print("V3 task plan analysis")
    print(f"- source: {report['source_path']}")
    print(f"- tasks: {report['task_count']}")
    print(f"- plan options: {report['total_plan_options']} avg={report['avg_plans_per_task']}")
    print(f"- baseline plan_1 conflicts: {baseline['hard_conflicts']} {baseline['conflict_summary']}")
    print(
        "- low diversity tasks: "
        f"{diversity['low_diversity_task_count']} rate={diversity['low_diversity_task_rate']}"
    )
    print("- top slots by task count:")
    for item in hotspots["top_slots_by_task_count"][:10]:
        print(f"  day={item['day_of_week']} period={item['period_index']} tasks={item['count']}")
    print("- top rooms by task count:")
    for item in hotspots["top_rooms_by_task_count"][:10]:
        print(f"  room={item['classroom_name']}#{item['classroom_id']} tasks={item['count']}")
    print("- top resources by task count:")
    for item in hotspots["top_resources_by_task_count"][:10]:
        print(
            "  "
            f"day={item['day_of_week']} period={item['period_index']} "
            f"room={item['classroom_name']}#{item['classroom_id']} tasks={item['count']}"
        )
    if "scheme_comparison" in report:
        print("- scheme comparison:")
        for item in report["scheme_comparison"]["schemes"]:
            print(
                "  "
                f"scheme={item['scheme_index']} conflicts={item['hard_conflicts']} "
                f"improvement={item['improvement_vs_plan_1']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze V3 task plan diversity and conflict baseline.")
    parser.add_argument("task_plans_path")
    parser.add_argument("--scheme-path", default=None)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--output", default=None)
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    args = parser.parse_args()
    report = analyze_task_plans(
        args.task_plans_path,
        scheme_path=args.scheme_path,
        top_n=args.top_n,
    )
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)


if __name__ == "__main__":
    main()
