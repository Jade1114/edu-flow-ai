"""Validate V3.5 DB-shaped dry-run export."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from export_template_cover_to_db_draft import DEFAULT_OUTPUT_DIR

DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_DIR / "validation_report.json"


def validate(output_dir: Path = DEFAULT_OUTPUT_DIR, report_path: Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    templates = _read_jsonl(output_dir / "schedule_templates.jsonl")
    weeks = _read_jsonl(output_dir / "schedule_template_weeks.jsonl")
    fragments = _read_jsonl(output_dir / "schedule_template_fragments.jsonl")
    slots = _read_jsonl(output_dir / "schedule_template_fragment_slots.jsonl")

    issues: list[dict[str, Any]] = []
    template_ids = {row["id"] for row in templates}
    template_codes = {row["template_code"] for row in templates}
    fragment_ids = {row["id"] for row in fragments}
    fragment_codes = {(row["template_code"], row["fragment_code"]) for row in fragments}

    for row in weeks:
        if row["template_id"] not in template_ids:
            issues.append({"issue": "week_missing_template_id", "row": row})
        if row["template_code"] not in template_codes:
            issues.append({"issue": "week_missing_template_code", "row": row})

    for row in fragments:
        if row["template_id"] not in template_ids:
            issues.append({"issue": "fragment_missing_template_id", "row": row})
        if row["template_code"] not in template_codes:
            issues.append({"issue": "fragment_missing_template_code", "row": row})

    for row in slots:
        if row["template_fragment_id"] not in fragment_ids:
            issues.append({"issue": "slot_missing_fragment_id", "row": row})
        if (row["template_code"], row["fragment_code"]) not in fragment_codes:
            issues.append({"issue": "slot_missing_fragment_code", "row": row})
        if row["template_id"] not in template_ids:
            issues.append({"issue": "slot_missing_template_id", "row": row})

    expected_slots = sum(_safe_int(row.get("consecutive_slots")) for row in fragments)
    if expected_slots != len(slots):
        issues.append({"issue": "slot_count_mismatch", "expected": expected_slots, "actual": len(slots)})

    week_numbers = sorted(_safe_int(row["week_number"]) for row in weeks)
    if week_numbers != list(range(1, len(weeks) + 1)):
        issues.append({"issue": "week_numbers_not_continuous", "week_numbers": week_numbers})

    report = {
        "counts": {
            "templates": len(templates),
            "weeks": len(weeks),
            "fragments": len(fragments),
            "slots": len(slots),
        },
        "template_codes": sorted(template_codes),
        "week_template_distribution": dict(Counter(row["template_code"] for row in weeks).most_common()),
        "fragment_template_distribution": dict(Counter(row["template_code"] for row in fragments).most_common()),
        "slot_template_distribution": dict(Counter(row["template_code"] for row in slots).most_common()),
        "issue_count": len(issues),
        "issue_counts": dict(Counter(issue["issue"] for issue in issues).most_common()),
        "issues_preview": issues[:50],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate V3.5 DB dry-run export files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    report = validate(Path(args.output_dir), Path(args.report))
    print(json.dumps({k: v for k, v in report.items() if k != "issues_preview"}, ensure_ascii=False, indent=2))
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
