"""Import V3.5 DB dry-run JSONL files into MySQL.

Safe by default:
  - Without --execute, only validates files and checks table availability.
  - With --execute, inserts rows in one transaction.

Run from backend/python so `app.db.session` can load the project .env.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from export_template_cover_db_draft import DEFAULT_OUTPUT_DIR

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import connect, load_db_config  # noqa: E402

TABLE_FILES = {
    "schedule_template": "schedule_templates.jsonl",
    "schedule_template_week": "schedule_template_weeks.jsonl",
    "schedule_template_fragment": "schedule_template_fragments.jsonl",
    "schedule_template_fragment_slot": "schedule_template_fragment_slots.jsonl",
}

INSERT_COLUMNS = {
    "schedule_template": [
        "id", "allocation_task_id", "template_code", "template_name", "template_order",
        "source_type", "algorithm_version", "status", "fragment_count", "task_count",
    ],
    "schedule_template_week": [
        "id", "allocation_task_id", "week_number", "template_id", "template_code", "source_type", "notes",
    ],
    "schedule_template_fragment": [
        "id", "template_id", "template_code", "allocation_task_id", "fragment_code",
        "teaching_task_id", "source_key", "course_id", "course_name", "teacher_id", "teacher_name",
        "class_group_id", "class_name", "classroom_id", "classroom_name", "day_of_week", "period_index",
        "consecutive_slots", "required_room_type", "source_type", "lock_status", "score", "candidate_rank",
    ],
    "schedule_template_fragment_slot": [
        "template_fragment_id", "fragment_code", "template_id", "template_code", "allocation_task_id",
        "teaching_task_id", "classroom_id", "teacher_id", "class_group_id", "day_of_week", "period_index",
    ],
}


def import_draft(*, input_dir: Path = DEFAULT_OUTPUT_DIR, execute: bool = False, truncate: bool = False) -> dict[str, Any]:
    rows_by_table = {table: _read_jsonl(input_dir / filename) for table, filename in TABLE_FILES.items()}
    config = load_db_config()
    connection = connect(config)
    try:
        existing_tables = _existing_tables(connection)
        missing_tables = [table for table in TABLE_FILES if table not in existing_tables]
        report = {
            "database": config.database,
            "input_dir": str(input_dir),
            "execute": execute,
            "truncate": truncate,
            "counts": {table: len(rows) for table, rows in rows_by_table.items()},
            "missing_tables": missing_tables,
        }
        if missing_tables:
            report["status"] = "missing_tables"
            return report
        if not execute:
            report["status"] = "dry_run_ok"
            return report

        with connection.cursor() as cursor:
            if truncate:
                _truncate_tables(cursor)
            for table in [
                "schedule_template",
                "schedule_template_week",
                "schedule_template_fragment",
                "schedule_template_fragment_slot",
            ]:
                _insert_rows(cursor, table, rows_by_table[table])
        connection.commit()
        report["status"] = "inserted"
        return report
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _existing_tables(connection) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        rows = cursor.fetchall()
    result = set()
    for row in rows:
        result.update(str(value) for value in row.values())
    return result


def _truncate_tables(cursor) -> None:
    for table in [
        "schedule_template_fragment_slot",
        "schedule_template_fragment",
        "schedule_template_week",
        "schedule_template",
    ]:
        cursor.execute(f"TRUNCATE TABLE {table}")


def _insert_rows(cursor, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = INSERT_COLUMNS[table]
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    values = [tuple(row.get(column) for column in columns) for row in rows]
    cursor.executemany(sql, values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import V3.5 DB dry-run JSONL files into MySQL.")
    parser.add_argument("--input-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="Actually insert rows. Default is dry-run only.")
    parser.add_argument("--truncate", action="store_true", help="Truncate target template tables before inserting. Requires --execute.")
    args = parser.parse_args()
    if args.truncate and not args.execute:
        raise SystemExit("--truncate requires --execute")

    report = import_draft(input_dir=Path(args.input_dir), execute=args.execute, truncate=args.truncate)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
