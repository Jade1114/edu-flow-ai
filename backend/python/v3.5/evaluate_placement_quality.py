"""Evaluate V3.5 placement model quality on real timetable-derived samples.

This script focuses on downstream scheduling usefulness:
  1. Are predicted resources diverse enough?
  2. Are predictions close to historical placements?
  3. If each task takes Top1 placement, how many template conflicts appear?
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from placement_model import DATA_PATH, OUTPUT_DIR, RESOURCE_KEY, SLOT_LABEL, V35PlacementModel, _load_training_frame
from placement_single_model import OUTPUT_DIR as SINGLE_OUTPUT_DIR
from placement_single_model import V35SinglePlacementModel

DEFAULT_REPORT_PATH = OUTPUT_DIR / "quality_report.json"


def evaluate(
    *,
    data_path: Path = DATA_PATH,
    model_dir: Path = OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    top_k: int = 30,
    slot_top_k: int = 10,
    limit: int | None = None,
    model_type: str = "two-stage",
) -> dict[str, Any]:
    df = _load_training_frame(data_path)
    if model_type == "single":
        model = V35SinglePlacementModel.load(model_dir)
    elif model_type == "two-stage":
        model = V35PlacementModel.load(model_dir)
    else:
        raise ValueError(f"Unsupported model_type: {model_type}")

    decisions: list[dict[str, Any]] = []
    hit_counts = {1: 0, 5: 0, 10: 0, 30: 0}
    slot_hit_counts = {1: 0, 3: 0, 5: 0}
    empty_predictions = 0

    grouped_items = list(df.groupby("source_key", dropna=False))
    if limit is not None:
        grouped_items = grouped_items[:limit]

    for source_key, group in grouped_items:
        task = group.iloc[0].to_dict()
        truth_resources = set(group[RESOURCE_KEY].astype(str).tolist())
        truth_slots = set(group[SLOT_LABEL].astype(str).tolist())
        predictions = model.predict_topk(task, top_k=top_k, slot_top_k=slot_top_k)

        if not predictions:
            empty_predictions += 1
            continue

        predicted_resources = [candidate.resource_key for candidate in predictions]
        predicted_slots = [f"{candidate.day_of_week}|{candidate.period_index}" for candidate in predictions]
        for k in hit_counts:
            if truth_resources & set(predicted_resources[: min(k, len(predicted_resources))]):
                hit_counts[k] += 1
        for k in slot_hit_counts:
            if truth_slots & set(predicted_slots[: min(k, len(predicted_slots))]):
                slot_hit_counts[k] += 1

        best = predictions[0]
        decisions.append(
            {
                "source_key": str(source_key),
                "course_name": str(task.get("course_name") or ""),
                "course_code": str(task.get("course_code") or ""),
                "teacher_name": str(task.get("teacher_name") or ""),
                "class_name": str(task.get("class_name") or ""),
                "required_room_type": str(task.get("required_room_type") or ""),
                "truth_resources": sorted(truth_resources),
                "truth_slots": sorted(truth_slots),
                "predicted_resource": best.resource_key,
                "predicted_slot": f"{best.day_of_week}|{best.period_index}",
                "predicted_classroom": best.classroom_name,
                "predicted_day_of_week": best.day_of_week,
                "predicted_period_index": best.period_index,
                "score": best.score,
                "source": best.source,
                "topk_resources": predicted_resources,
            }
        )

    total = len(decisions)
    resource_stats = _resource_diversity(decisions)
    conflict_report = _conflicts(decisions)
    denominator = max(1, total)

    report = {
        "input": {
            "data_path": str(data_path),
            "model_dir": str(model_dir),
            "top_k": top_k,
            "slot_top_k": slot_top_k,
            "limit": limit,
            "model_type": model_type,
        },
        "sample_stats": {
            "task_count": total,
            "empty_predictions": empty_predictions,
        },
        "closeness": {
            **{f"hit@{k}": round(hit_counts[k] / denominator, 6) for k in sorted(hit_counts)},
            **{f"slot_hit@{k}": round(slot_hit_counts[k] / denominator, 6) for k in sorted(slot_hit_counts)},
        },
        "resource_diversity": resource_stats,
        "conflicts": conflict_report,
        "decisions_preview": decisions[:20],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _resource_diversity(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(decisions)
    resource_counts = Counter(decision["predicted_resource"] for decision in decisions)
    slot_counts = Counter(decision["predicted_slot"] for decision in decisions)
    room_counts = Counter(decision["predicted_classroom"] for decision in decisions)
    candidate_resources = [resource for decision in decisions for resource in decision.get("topk_resources", [])]
    candidate_counts = Counter(candidate_resources)
    per_task_unique_topk = [len(set(decision.get("topk_resources", []))) for decision in decisions]

    unique_resources = len(resource_counts)
    repeated_assignments = sum(count - 1 for count in resource_counts.values() if count > 1)
    duplicate_rate = repeated_assignments / max(1, total)
    candidate_repeated = sum(count - 1 for count in candidate_counts.values() if count > 1)

    return {
        "assignment_count": total,
        "unique_resource_count": unique_resources,
        "resource_duplicate_assignments": repeated_assignments,
        "resource_duplicate_rate": round(duplicate_rate, 6),
        "unique_slot_count": len(slot_counts),
        "unique_room_count": len(room_counts),
        "topk_candidate_count": len(candidate_resources),
        "topk_unique_resource_count": len(candidate_counts),
        "topk_duplicate_assignments": candidate_repeated,
        "topk_duplicate_rate": round(candidate_repeated / max(1, len(candidate_resources)), 6),
        "avg_unique_topk_per_task": round(sum(per_task_unique_topk) / max(1, total), 6),
        "top_repeated_resources": _counter_items(resource_counts, limit=20, min_count=2),
        "top_repeated_slots": _counter_items(slot_counts, limit=20, min_count=2),
        "top_repeated_rooms": _counter_items(room_counts, limit=20, min_count=2),
        "topk_repeated_resources": _counter_items(candidate_counts, limit=20, min_count=2),
    }


def _conflicts(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    teacher = _group_conflicts(decisions, key_fields=("teacher_name", "predicted_slot"), ignore_empty_field="teacher_name")
    class_group = _group_conflicts(decisions, key_fields=("class_name", "predicted_slot"), ignore_empty_field="class_name")
    room = _group_conflicts(decisions, key_fields=("predicted_classroom", "predicted_slot"), ignore_empty_field="predicted_classroom")

    hard_conflict_source_keys = set()
    for bucket in (teacher, class_group, room):
        for item in bucket["items"]:
            hard_conflict_source_keys.update(item["source_keys"])

    total = len(decisions)
    return {
        "hard_conflict_task_count": len(hard_conflict_source_keys),
        "hard_conflict_task_rate": round(len(hard_conflict_source_keys) / max(1, total), 6),
        "teacher_conflicts": teacher,
        "class_conflicts": class_group,
        "room_conflicts": room,
    }


def _group_conflicts(
    decisions: list[dict[str, Any]],
    *,
    key_fields: tuple[str, str],
    ignore_empty_field: str,
    limit: int = 50,
) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        if not str(decision.get(ignore_empty_field) or "").strip():
            continue
        key = tuple(str(decision.get(field) or "") for field in key_fields)
        buckets[key].append(decision)

    items = []
    conflict_assignment_count = 0
    for key, bucket in buckets.items():
        if len(bucket) <= 1:
            continue
        conflict_assignment_count += len(bucket)
        items.append(
            {
                "key": "|".join(key),
                "count": len(bucket),
                "source_keys": [item["source_key"] for item in bucket],
                "courses": [item["course_name"] for item in bucket],
                "classes": [item["class_name"] for item in bucket],
                "teachers": [item["teacher_name"] for item in bucket],
                "resources": [item["predicted_resource"] for item in bucket],
            }
        )

    items.sort(key=lambda item: item["count"], reverse=True)
    return {
        "group_count": len(items),
        "assignment_count": conflict_assignment_count,
        "items": items[:limit],
    }


def _counter_items(counter: Counter[str], *, limit: int, min_count: int) -> list[dict[str, Any]]:
    return [
        {"key": key, "count": count}
        for key, count in counter.most_common(limit)
        if count >= min_count
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate V3.5 placement quality on real timetable samples.")
    parser.add_argument("--data", default=str(DATA_PATH))
    parser.add_argument("--model-type", choices=["two-stage", "single"], default="two-stage")
    parser.add_argument("--model-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--slot-top-k", type=int, default=10)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    report = evaluate(
        data_path=Path(args.data),
        model_dir=Path(args.model_dir),
        report_path=Path(args.report),
        top_k=args.top_k,
        slot_top_k=args.slot_top_k,
        limit=args.limit,
        model_type=args.model_type,
    )

    print(json.dumps({
        "sample_stats": report["sample_stats"],
        "closeness": report["closeness"],
        "resource_diversity": report["resource_diversity"],
        "conflicts_summary": {
            "hard_conflict_task_count": report["conflicts"]["hard_conflict_task_count"],
            "hard_conflict_task_rate": report["conflicts"]["hard_conflict_task_rate"],
            "teacher_groups": report["conflicts"]["teacher_conflicts"]["group_count"],
            "class_groups": report["conflicts"]["class_conflicts"]["group_count"],
            "room_groups": report["conflicts"]["room_conflicts"]["group_count"],
        },
        "report_path": str(Path(args.report)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
