"""Diagnose whether historical timetable placements can replay allocation tasks."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml.scheduling_v2.data_loader import load_context

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "real-dataset"


@dataclass(frozen=True)
class HistoricalPlacement:
    course_code: str
    teacher: str
    class_group: str
    week: int
    day: int
    period: int
    room: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose exact historical placement replay coverage.")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="Directory containing real-dataset jsonl files.")
    parser.add_argument("--allocation-task-id", type=int, default=None, help="Optional DB allocation task id to diagnose.")
    parser.add_argument("--top", type=int, default=20, help="Number of misses/hotspots to print.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    history = build_historical_placement_index(data_dir)
    targets = load_allocation_targets(args.allocation_task_id) if args.allocation_task_id else load_training_targets(data_dir)
    report = diagnose_targets(targets, history, top=args.top)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_historical_placement_index(data_dir: Path = DATA_DIR) -> dict[tuple[str, str, str], list[HistoricalPlacement]]:
    teaching_tasks = _load_jsonl(data_dir / "teaching_tasks.jsonl")
    timetables = _load_jsonl(data_dir / "timetables.jsonl")
    teachers_by_course_class: dict[tuple[str, str], set[str]] = defaultdict(set)
    for task in teaching_tasks:
        course_code = _norm(task.get("course_code"))
        teacher = _norm(task.get("teacher"))
        class_group = _norm(task.get("class_group"))
        if course_code and teacher and class_group:
            teachers_by_course_class[(course_code, class_group)].add(teacher)

    index: dict[tuple[str, str, str], list[HistoricalPlacement]] = defaultdict(list)
    for row in timetables:
        course_code = _norm(row.get("course_code"))
        class_group = _norm(row.get("class_group"))
        room = _norm(row.get("room"))
        if not course_code or not class_group or not room:
            continue
        teachers = teachers_by_course_class.get((course_code, class_group), set())
        if not teachers:
            continue
        placement = {
            "course_code": course_code,
            "class_group": class_group,
            "week": _as_int(row.get("week")),
            "day": _as_int(row.get("day")),
            "period": _period_start_to_index(row.get("period_start")),
            "room": room,
        }
        if placement["week"] <= 0 or placement["day"] <= 0 or placement["period"] <= 0:
            continue
        for teacher in teachers:
            index[(course_code, teacher, class_group)].append(HistoricalPlacement(
                teacher=teacher,
                **placement,
            ))
    return {key: sorted(values, key=lambda p: (p.week, p.day, p.period, p.room)) for key, values in index.items()}


def load_training_targets(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
    return [
        {
            "teaching_task_id": index + 1,
            "course_code": _norm(row.get("course_code")),
            "teacher": _norm(row.get("teacher")),
            "class_groups": [_norm(row.get("class_group"))],
            "source": "training_jsonl",
        }
        for index, row in enumerate(_load_jsonl(data_dir / "teaching_tasks.jsonl"))
        if _norm(row.get("course_code")) and _norm(row.get("teacher")) and _norm(row.get("class_group"))
    ]


def load_allocation_targets(allocation_task_id: int) -> list[dict[str, Any]]:
    context = load_context(allocation_task_id)
    targets: list[dict[str, Any]] = []
    for task in context.tasks:
        class_groups = [
            _norm(name)
            for name in str(task.raw.get("class_group_names") or "").split(",")
            if _norm(name)
        ]
        targets.append({
            "teaching_task_id": task.teaching_task_id,
            "course_code": _norm(task.raw.get("course_code")),
            "teacher": _norm(task.teacher_name),
            "class_groups": class_groups,
            "source": f"allocation_task:{allocation_task_id}",
        })
    return targets


def diagnose_targets(
    targets: list[dict[str, Any]],
    history: dict[tuple[str, str, str], list[HistoricalPlacement]],
    *,
    top: int = 20,
) -> dict[str, Any]:
    hits = 0
    partial_hits = 0
    misses: list[dict[str, Any]] = []
    replayed: list[tuple[dict[str, Any], HistoricalPlacement]] = []
    placements_per_task: list[int] = []

    for target in targets:
        class_groups = target.get("class_groups") or []
        matched: list[HistoricalPlacement] = []
        missing_groups: list[str] = []
        for class_group in class_groups:
            key = (_norm(target.get("course_code")), _norm(target.get("teacher")), _norm(class_group))
            placements = history.get(key, [])
            if placements:
                matched.extend(placements)
            else:
                missing_groups.append(class_group)
        if matched and not missing_groups:
            hits += 1
        elif matched:
            partial_hits += 1
        else:
            misses.append({
                "teaching_task_id": target.get("teaching_task_id"),
                "course_code": target.get("course_code"),
                "teacher": target.get("teacher"),
                "class_groups": class_groups,
            })
        placements_per_task.append(len(matched))
        replayed.extend((target, placement) for placement in matched)

    conflicts = detect_replay_conflicts(replayed)
    total = len(targets)
    return {
        "total_tasks": total,
        "exact_hits": hits,
        "partial_hits": partial_hits,
        "misses": len(misses),
        "exact_hit_rate": round(hits / total, 4) if total else 0.0,
        "covered_tasks": hits + partial_hits,
        "covered_rate": round((hits + partial_hits) / total, 4) if total else 0.0,
        "total_replayed_placements": len(replayed),
        "avg_placements_per_task": round(sum(placements_per_task) / max(1, total), 2),
        "conflicts": conflicts,
        "sample_misses": misses[:top],
    }


def detect_replay_conflicts(replayed: list[tuple[dict[str, Any], HistoricalPlacement]]) -> dict[str, Any]:
    teacher_usage: dict[tuple[str, int, int, int], list[dict[str, Any]]] = defaultdict(list)
    class_usage: dict[tuple[str, int, int, int], list[dict[str, Any]]] = defaultdict(list)
    room_usage: dict[tuple[str, int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for target, placement in replayed:
        task_id = int(target.get("teaching_task_id") or 0)
        slot = (placement.week, placement.day, placement.period)
        item = {
            "task_id": task_id,
            "course_code": placement.course_code,
            "teacher": placement.teacher,
            "class_group": placement.class_group,
            "room": placement.room,
        }
        teacher_usage[(placement.teacher, *slot)].append(item)
        class_usage[(placement.class_group, *slot)].append(item)
        room_usage[(placement.room, *slot)].append(item)
    return {
        "TEACHER_TIME": _conflict_summary(teacher_usage),
        "CLASS_GROUP_TIME": _conflict_summary(class_usage),
        "CLASSROOM_TIME": _conflict_summary(room_usage),
    }


def _conflict_summary(usage: dict[tuple[Any, ...], list[dict[str, Any]]]) -> dict[str, Any]:
    hotspots = []
    mergeable = []
    for key, items in usage.items():
        task_ids = {int(item["task_id"]) for item in items}
        if len(task_ids) <= 1:
            continue
        session_keys = {
            (
                item["course_code"],
                item["teacher"],
                item["room"],
            )
            for item in items
        }
        entry = {
            "key": key,
            "count": len(items),
            "task_ids": sorted(task_ids)[:10],
            "session_count": len(session_keys),
            "sessions": sorted(session_keys)[:5],
        }
        if len(session_keys) == 1:
            mergeable.append(entry)
        else:
            hotspots.append(entry)
    hotspots.sort(key=lambda item: (-item["count"], str(item["key"])))
    mergeable.sort(key=lambda item: (-item["count"], str(item["key"])))
    return {
        "conflict_slots": len(hotspots),
        "conflict_records": sum(item["count"] for item in hotspots),
        "mergeable_joint_slots": len(mergeable),
        "mergeable_joint_records": sum(item["count"] for item in mergeable),
        "top": hotspots[:20],
        "top_mergeable": mergeable[:20],
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm(value: Any) -> str:
    return str(value or "").strip().replace(" ", "")


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _period_start_to_index(value: Any) -> int:
    start = _as_int(value)
    if start <= 0:
        return 0
    return (start + 1) // 2


if __name__ == "__main__":
    main()
