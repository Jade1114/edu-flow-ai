"""Batch process class schedule Excel imports.

For each .xls/.xlsx under input-dir:
1. parse_schedule_excel.py logic: Excel -> CSV
2. csv_to_jsonl.py logic: CSV -> JSONL
3. analyze_schedule_import.py logic: DB comparison report
4. prepare_import_review.py logic: human-review decision CSV

This script is read-only against the database. It does not apply decisions.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analyze_schedule_import import analyze
from csv_to_jsonl import convert_dir
from parse_schedule_excel import DEFAULT_OUTPUT_ROOT, parse_schedule_excel
from prepare_import_review import prepare_review

DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "schedules"
DEFAULT_BATCH_REPORT_PATH = DEFAULT_OUTPUT_ROOT / "batch_process_report.json"


DEFAULT_TRAINING_OUTPUT_ROOT = DEFAULT_OUTPUT_ROOT.parent / "schedule_imports_training"


def batch_process(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    task_batch: str = "DEFAULT",
    fail_fast: bool = False,
    training: bool = False,
) -> dict[str, Any]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"input-dir not found: {input_dir}")
    files = sorted([path for path in input_dir.rglob("*") if path.suffix.lower() in {".xls", ".xlsx"}])
    if training:
        output_root = DEFAULT_TRAINING_OUTPUT_ROOT
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for path in files:
        output_dir = _unique_output_dir(output_root, path)
        try:
            _clean_stale_analysis_jsonl(output_dir)
            parse_report = parse_schedule_excel(input_path=path, output_dir=output_dir, task_batch=task_batch)
            jsonl_report = convert_dir(input_dir=output_dir)
            item: dict[str, Any] = {
                "status": "ok",
                "input_path": str(path),
                "output_dir": str(output_dir),
                "parse_counts": parse_report.get("counts", {}),
                "jsonl": {"file_count": jsonl_report.get("file_count"), "total_rows": jsonl_report.get("total_rows")},
            }
            if not training:
                analysis_report = analyze(input_dir=output_dir)
                review_report = prepare_review(input_dir=output_dir)
                item["analysis"] = analysis_report.get("counts", {})
                item["conflict_counts"] = analysis_report.get("conflict_counts", {})
                item["new_item_counts"] = analysis_report.get("new_item_counts", {})
                item["review"] = review_report.get("counts", {})
            results.append(item)
        except Exception as exc:  # noqa: BLE001 - batch report should capture per-file failures
            item = {
                "status": "failed",
                "input_path": str(path),
                "output_dir": str(output_dir),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            results.append(item)
            if fail_fast:
                raise

    report = {
        "status": "ok" if all(item["status"] == "ok" for item in results) else "failed",
        "input_dir": str(input_dir),
        "output_root": str(output_root),
        "task_batch": task_batch,
        "file_count": len(files),
        "success_count": sum(1 for item in results if item["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["status"] != "ok"),
        "aggregate": _aggregate(results),
        "items": results,
    }
    (output_root / "batch_process_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _clean_stale_analysis_jsonl(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    for path in output_dir.glob("import_*.jsonl"):
        path.unlink()


def _unique_output_dir(output_root: Path, input_path: Path) -> Path:
    stem = input_path.stem
    candidate = output_root / stem
    if not candidate.exists():
        return candidate
    # Reuse same deterministic directory for the same source file; parsing overwrites CSVs.
    return candidate


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate_counts: Counter[str] = Counter()
    conflict_counts: Counter[str] = Counter()
    new_item_counts: Counter[str] = Counter()
    review_counts: Counter[str] = Counter()
    for item in results:
        if item.get("status") != "ok":
            continue
        for key, value in (item.get("parse_counts") or {}).items():
            aggregate_counts[f"parse_{key}"] += int(value or 0)
        for key, value in (item.get("conflict_counts") or {}).items():
            conflict_counts[key] += int(value or 0)
        for key, value in (item.get("new_item_counts") or {}).items():
            new_item_counts[key] += int(value or 0)
        for key, value in (item.get("review") or {}).items():
            review_counts[key] += int(value or 0)
    return {
        "parse_counts": dict(sorted(aggregate_counts.items())),
        "conflict_counts": dict(sorted(conflict_counts.items())),
        "new_item_counts": dict(sorted(new_item_counts.items())),
        "review_counts": dict(sorted(review_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch process schedule Excel imports.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--task-batch", default="DEFAULT")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--training", action="store_true", help="Skip analysis and review; output to schedule_imports_training/")
    args = parser.parse_args()
    report = batch_process(
        input_dir=Path(args.input_dir),
        output_root=Path(args.output_root),
        task_batch=args.task_batch,
        fail_fast=args.fail_fast,
        training=args.training,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "items"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
