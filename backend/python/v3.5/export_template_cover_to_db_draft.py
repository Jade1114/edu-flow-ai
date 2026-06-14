"""Export V3.5 template cover result into DB-shaped dry-run JSONL files.

This script does not connect to the database. It transforms
`template_cover_v1.json` into records matching the planned template tables:

- schedule_templates.jsonl
- schedule_template_weeks.jsonl
- schedule_template_fragments.jsonl
- schedule_template_fragment_slots.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from placement_model import OUTPUT_DIR as PLACEMENT_OUTPUT_DIR

DEFAULT_INPUT_PATH = PLACEMENT_OUTPUT_DIR / "template_cover_v1.json"
DEFAULT_OUTPUT_DIR = PLACEMENT_OUTPUT_DIR / "db_draft"
DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_DIR / "export_report.json"

ALGORITHM_VERSION = "v3.5-cover-v1"


def export_draft(
    *,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    allocation_task_id: int = 1,
    total_weeks: int = 18,
) -> dict[str, Any]:
    cover = json.loads(input_path.read_text(encoding="utf-8"))
    templates = cover.get("templates", [])
    output_dir.mkdir(parents=True, exist_ok=True)

    template_rows = _build_template_rows(templates, allocation_task_id)
    template_id_by_code = {row["template_code"]: row["id"] for row in template_rows}
    week_rows = _build_week_rows(templates, template_id_by_code, allocation_task_id, total_weeks)
    fragment_rows, fragment_id_by_code = _build_fragment_rows(templates, template_id_by_code, allocation_task_id)
    slot_rows = _build_slot_rows(templates, template_id_by_code, fragment_id_by_code, allocation_task_id)

    paths = {
        "schedule_templates": output_dir / "schedule_templates.jsonl",
        "schedule_template_weeks": output_dir / "schedule_template_weeks.jsonl",
        "schedule_template_fragments": output_dir / "schedule_template_fragments.jsonl",
        "schedule_template_fragment_slots": output_dir / "schedule_template_fragment_slots.jsonl",
    }
    _write_jsonl(paths["schedule_templates"], template_rows)
    _write_jsonl(paths["schedule_template_weeks"], week_rows)
    _write_jsonl(paths["schedule_template_fragments"], fragment_rows)
    _write_jsonl(paths["schedule_template_fragment_slots"], slot_rows)

    report = _build_report(template_rows, week_rows, fragment_rows, slot_rows, paths, allocation_task_id, total_weeks)
    (output_dir / "export_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _build_template_rows(templates: list[dict[str, Any]], allocation_task_id: int) -> list[dict[str, Any]]:
    rows = []
    for index, template in enumerate(templates, start=1):
        fragments = template.get("fragments", [])
        rows.append({
            "id": index,
            "allocation_task_id": allocation_task_id,
            "template_code": str(template.get("template_id") or f"template_{index}"),
            "template_name": f"V3.5 模板 {index}",
            "template_order": index,
            "source_type": "AUTO",
            "algorithm_version": ALGORITHM_VERSION,
            "status": "ACTIVE",
            "fragment_count": len(fragments),
            "task_count": len({fragment.get("source_key") for fragment in fragments}),
        })
    return rows


def _build_week_rows(
    templates: list[dict[str, Any]],
    template_id_by_code: dict[str, int],
    allocation_task_id: int,
    total_weeks: int,
) -> list[dict[str, Any]]:
    week_template = _choose_template_by_week(templates, total_weeks)
    rows = []
    for week_number in range(1, total_weeks + 1):
        template_code = week_template.get(week_number) or _first_template_code(templates)
        rows.append({
            "id": week_number,
            "allocation_task_id": allocation_task_id,
            "week_number": week_number,
            "template_id": template_id_by_code[template_code],
            "template_code": template_code,
            "source_type": "AUTO",
            "notes": "dry-run generated from template fragment week masks",
        })
    return rows


def _choose_template_by_week(templates: list[dict[str, Any]], total_weeks: int) -> dict[int, str]:
    scores: dict[int, Counter[str]] = {week: Counter() for week in range(1, total_weeks + 1)}
    for template in templates:
        template_code = str(template.get("template_id"))
        for fragment in template.get("fragments", []):
            for week in fragment.get("week_mask") or []:
                week_number = _safe_int(week)
                if 1 <= week_number <= total_weeks:
                    scores[week_number][template_code] += 1
    result = {}
    fallback = _first_template_code(templates)
    for week, counter in scores.items():
        if counter:
            result[week] = counter.most_common(1)[0][0]
        else:
            result[week] = fallback
    return result


def _build_fragment_rows(
    templates: list[dict[str, Any]],
    template_id_by_code: dict[str, int],
    allocation_task_id: int,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    rows = []
    fragment_id_by_code: dict[tuple[str, str], int] = {}
    next_id = 1
    for template in templates:
        template_code = str(template.get("template_id"))
        template_id = template_id_by_code[template_code]
        for fragment in template.get("fragments", []):
            fragment_code = str(fragment.get("fragment_id"))
            row = {
                "id": next_id,
                "template_id": template_id,
                "template_code": template_code,
                "allocation_task_id": allocation_task_id,
                "fragment_code": fragment_code,
                "teaching_task_id": _safe_int(fragment.get("teaching_task_id")) or None,
                "source_key": fragment.get("source_key"),
                "course_id": None,
                "course_name": fragment.get("course_name"),
                "teacher_id": None,
                "teacher_name": fragment.get("teacher_name"),
                "class_group_id": None,
                "class_name": fragment.get("class_names") or fragment.get("class_group_names") or fragment.get("class_name"),
                "classroom_id": None,
                "classroom_name": fragment.get("classroom_name"),
                "day_of_week": _safe_int(fragment.get("day_of_week")),
                "period_index": _safe_int(fragment.get("period_index")),
                "consecutive_slots": _safe_int(fragment.get("consecutive_slots")),
                "required_room_type": fragment.get("required_room_type"),
                "source_type": "AUTO",
                "lock_status": "UNLOCKED",
                "score": fragment.get("score"),
                "candidate_rank": fragment.get("candidate_rank"),
            }
            rows.append(row)
            fragment_id_by_code[(template_code, fragment_code)] = next_id
            next_id += 1
    return rows, fragment_id_by_code


def _build_slot_rows(
    templates: list[dict[str, Any]],
    template_id_by_code: dict[str, int],
    fragment_id_by_code: dict[tuple[str, str], int],
    allocation_task_id: int,
) -> list[dict[str, Any]]:
    rows = []
    next_id = 1
    for template in templates:
        template_code = str(template.get("template_id"))
        template_id = template_id_by_code[template_code]
        for fragment in template.get("fragments", []):
            fragment_code = str(fragment.get("fragment_id"))
            fragment_id = fragment_id_by_code[(template_code, fragment_code)]
            for segment in fragment.get("segments") or []:
                rows.append({
                    "id": next_id,
                    "template_fragment_id": fragment_id,
                    "fragment_code": fragment_code,
                    "template_id": template_id,
                    "template_code": template_code,
                    "allocation_task_id": allocation_task_id,
                    "teaching_task_id": _safe_int(fragment.get("teaching_task_id")) or None,
                    "classroom_id": None,
                    "teacher_id": None,
                    "class_group_id": None,
                    "day_of_week": _safe_int(segment.get("day_of_week")),
                    "period_index": _safe_int(segment.get("period_index")),
                })
                next_id += 1
    return rows


def _build_report(
    template_rows: list[dict[str, Any]],
    week_rows: list[dict[str, Any]],
    fragment_rows: list[dict[str, Any]],
    slot_rows: list[dict[str, Any]],
    paths: dict[str, Path],
    allocation_task_id: int,
    total_weeks: int,
) -> dict[str, Any]:
    return {
        "allocation_task_id": allocation_task_id,
        "total_weeks": total_weeks,
        "counts": {
            "schedule_templates": len(template_rows),
            "schedule_template_weeks": len(week_rows),
            "schedule_template_fragments": len(fragment_rows),
            "schedule_template_fragment_slots": len(slot_rows),
        },
        "week_template_distribution": dict(Counter(row["template_code"] for row in week_rows).most_common()),
        "fragment_template_distribution": dict(Counter(row["template_code"] for row in fragment_rows).most_common()),
        "slot_template_distribution": dict(Counter(row["template_code"] for row in slot_rows).most_common()),
        "paths": {key: str(path) for key, path in paths.items()},
        "preview": {
            "templates": template_rows[:5],
            "weeks": week_rows[:10],
            "fragments": fragment_rows[:5],
            "slots": slot_rows[:10],
        },
    }


def _first_template_code(templates: list[dict[str, Any]]) -> str:
    if not templates:
        raise ValueError("No templates found in cover result")
    return str(templates[0].get("template_id"))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Export V3.5 template cover to DB-shaped dry-run JSONL files.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--allocation-task-id", type=int, default=1)
    parser.add_argument("--total-weeks", type=int, default=18)
    args = parser.parse_args()

    report = export_draft(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        allocation_task_id=args.allocation_task_id,
        total_weeks=args.total_weeks,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "preview"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
