"""Validate iterative template cover v1."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from template_cover_v1 import DEFAULT_OUTPUT_PATH

DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_PATH.parent / "template_cover_v1_validation_report.json"


def validate_cover(*, cover_path: Path = DEFAULT_OUTPUT_PATH, report_path: Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    templates = cover.get("templates", [])
    issues: list[dict[str, Any]] = []
    template_summaries = []
    for template in templates:
        fragments = template.get("fragments", [])
        template_issues = []
        template_issues.extend(_occupancy_conflicts(fragments, "teacher_name", "teacher_conflict"))
        template_issues.extend(_occupancy_conflicts(fragments, "class_name", "class_conflict"))
        template_issues.extend(_occupancy_conflicts(fragments, "classroom_name", "room_conflict"))
        for issue in template_issues:
            issue["template_id"] = template.get("template_id")
        issues.extend(template_issues)
        template_summaries.append({
            "template_id": template.get("template_id"),
            "fragment_count": len(fragments),
            "task_count": len({fragment.get("source_key") for fragment in fragments}),
            "issue_count": len(template_issues),
        })

    all_fragments = [fragment for template in templates for fragment in template.get("fragments", [])]
    report = {
        "cover_id": cover.get("cover_id"),
        "template_count": len(templates),
        "fragment_count": len(all_fragments),
        "task_count": len({fragment.get("source_key") for fragment in all_fragments}),
        "issue_count": len(issues),
        "issue_counts": dict(Counter(issue["issue"] for issue in issues).most_common()),
        "templates": template_summaries,
        "issues_preview": issues[:80],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _occupancy_conflicts(fragments: list[dict[str, Any]], field: str, issue: str) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for fragment in fragments:
        owner = str(fragment.get(field) or "").strip()
        if not owner:
            continue
        for segment in fragment.get("segments") or []:
            buckets[(owner, _safe_int(segment.get("day_of_week")), _safe_int(segment.get("period_index")))].append(fragment)
    issues = []
    for key, bucket in buckets.items():
        if len(bucket) <= 1:
            continue
        issues.append({
            "issue": issue,
            "key": f"{key[0]}|{key[1]}|{key[2]}",
            "count": len(bucket),
            "fragment_ids": [fragment.get("fragment_id") for fragment in bucket],
            "source_keys": [fragment.get("source_key") for fragment in bucket],
        })
    return sorted(issues, key=lambda item: item["count"], reverse=True)


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate V3.5 template cover v1.")
    parser.add_argument("--cover", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    report = validate_cover(cover_path=Path(args.cover), report_path=Path(args.report))
    print(json.dumps({k: v for k, v in report.items() if k != "issues_preview"}, ensure_ascii=False, indent=2))
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
