"""Balanced V3 scheduling stress-data and run helper.

The script creates an allocation task with synthetic teaching_task rows spread
evenly across active teachers, class groups, and professional courses. Writes
are opt-in via --execute so --help and dry-runs are safe on developer machines.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_TASK_NAME = "v3-balanced-stress-4000"
DEFAULT_ALLOWED_WEEKS = ",".join(str(week) for week in range(1, 19))
DEFAULT_ALLOWED_WEEKDAYS = "1,2,3,4,5"
DEFAULT_ALLOWED_PERIODS = "1,2,3,4,5"


@dataclass(frozen=True)
class StressProfile:
    task_count: int = 4000
    placement_top_k: int = 64
    raw_plan_count: int = 64
    cp_plan_count: int = 16
    scheme_count: int = 1
    solver_time_limit_seconds: int = 1800
    generation_mode: str = "AUTO_QUALITY"
    max_auto_stage: str = "QUALITY_OPTIMIZATION"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and run a balanced 4000-level V3 scheduling stress chain."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Create or dry-run balanced teaching tasks in DB.")
    prepare.add_argument("--task-count", type=int, default=StressProfile.task_count)
    prepare.add_argument("--name", default=DEFAULT_TASK_NAME, help="allocation_task.name to create/use.")
    prepare.add_argument("--execute", action="store_true", help="Actually write DB rows. Omit for dry-run.")
    prepare.add_argument("--replace", action="store_true", help="Replace a previous generated task with the same name.")
    prepare.add_argument("--teacher-limit", type=int, default=None, help="Use only the first N active teachers.")
    prepare.add_argument("--class-limit", type=int, default=None, help="Use only the first N class groups.")
    prepare.add_argument("--course-limit", type=int, default=None, help="Use only the first N professional courses.")
    prepare.add_argument("--total-hours", type=int, default=2, help="total_hours per generated teaching task.")
    prepare.add_argument("--placement-top-k", type=int, default=StressProfile.placement_top_k)
    prepare.add_argument("--raw-plan-count", type=int, default=StressProfile.raw_plan_count)
    prepare.add_argument("--cp-plan-count", type=int, default=StressProfile.cp_plan_count)
    prepare.add_argument("--scheme-count", type=int, default=StressProfile.scheme_count)
    prepare.add_argument("--solver-time-limit-seconds", type=int, default=StressProfile.solver_time_limit_seconds)
    prepare.add_argument("--generation-mode", default=StressProfile.generation_mode)
    prepare.add_argument("--allowed-weeks", default=DEFAULT_ALLOWED_WEEKS)
    prepare.add_argument("--allowed-weekdays", default=DEFAULT_ALLOWED_WEEKDAYS)
    prepare.add_argument("--allowed-periods", default=DEFAULT_ALLOWED_PERIODS)

    run = subparsers.add_parser("run", help="Run the V3 pipeline with stress defaults.")
    run.add_argument("--allocation-task-id", type=int, required=True)
    run.add_argument("--output-dir", type=Path, default=None)
    run.add_argument("--top-k", type=int, default=StressProfile.placement_top_k)
    run.add_argument("--plan-count", type=int, default=StressProfile.raw_plan_count)
    run.add_argument("--cp-plan-count-note", type=int, default=StressProfile.cp_plan_count, help=argparse.SUPPRESS)
    run.add_argument("--scheme-count", type=int, default=StressProfile.scheme_count)
    run.add_argument("--solver-time-limit-seconds", type=float, default=StressProfile.solver_time_limit_seconds)
    run.add_argument("--generation-mode", default=StressProfile.generation_mode)
    run.add_argument("--max-auto-stage", default=StressProfile.max_auto_stage)
    run.add_argument("--skip-diversity", action="store_true", default=True)

    inspect = subparsers.add_parser("inspect-output", help="Summarize v3/auto summary JSON files.")
    inspect.add_argument("summary_path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        summary = prepare_balanced_data(args)
    elif args.command == "run":
        summary = run_stress_pipeline(args)
    else:
        summary = inspect_output(args.summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def prepare_balanced_data(args: argparse.Namespace) -> dict[str, Any]:
    from python.db.config import connect, load_db_config
    from python.db.repositories import ensure_default_time_slots

    profile = StressProfile(
        task_count=args.task_count,
        placement_top_k=args.placement_top_k,
        raw_plan_count=args.raw_plan_count,
        cp_plan_count=args.cp_plan_count,
        scheme_count=args.scheme_count,
        solver_time_limit_seconds=args.solver_time_limit_seconds,
        generation_mode=args.generation_mode,
    )
    if profile.task_count <= 0:
        raise ValueError("--task-count must be positive")
    if args.total_hours <= 0 or args.total_hours % 2 != 0:
        raise ValueError("--total-hours must be a positive even number")

    db = load_db_config()
    conn = connect(db)
    try:
        teachers = _limited(_fetch_teachers(conn), args.teacher_limit)
        class_groups = _limited(_fetch_class_groups(conn), args.class_limit)
        courses = _limited(_fetch_professional_courses(conn), args.course_limit)
        _require_pool("active teachers", teachers)
        _require_pool("class groups", class_groups)
        _require_pool("professional courses", courses)

        rows = _balanced_rows(
            task_count=profile.task_count,
            teachers=teachers,
            class_groups=class_groups,
            courses=courses,
            total_hours=args.total_hours,
        )
        distribution = _distribution(rows)
        summary: dict[str, Any] = {
            "dry_run": not args.execute,
            "allocation_task_name": args.name,
            "profile": asdict(profile),
            "pool_sizes": {
                "teachers": len(teachers),
                "class_groups": len(class_groups),
                "courses": len(courses),
            },
            "distribution": distribution,
            "sample_rows": rows[:5],
        }
        if not args.execute:
            summary["next_step"] = "Re-run with --execute to write DB rows."
            return summary

        ensure_default_time_slots(conn, weeks=20, weekdays=7, periods=5)
        with conn.cursor() as cursor:
            existing_id = _find_allocation_task_id(cursor, args.name)
            if existing_id and not args.replace:
                raise ValueError(
                    f"allocation_task name already exists: {args.name} (id={existing_id}); "
                    "use --replace to rebuild generated rows"
                )
            if existing_id and args.replace:
                _delete_generated_allocation(cursor, existing_id)
            cursor.execute("INSERT INTO allocation_task (name) VALUES (%s)", (args.name,))
            allocation_task_id = int(cursor.lastrowid)
            _insert_generation_config(cursor, allocation_task_id, args, profile)
            teaching_task_ids = _insert_teaching_tasks(cursor, allocation_task_id, rows)
        conn.commit()

        summary.update({
            "allocation_task_id": allocation_task_id,
            "inserted_teaching_task_count": len(teaching_task_ids),
            "first_teaching_task_id": teaching_task_ids[0] if teaching_task_ids else None,
            "last_teaching_task_id": teaching_task_ids[-1] if teaching_task_ids else None,
            "run_command": (
                "python ml/scripts/v3_balanced_stress.py run "
                f"--allocation-task-id {allocation_task_id}"
            ),
        })
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_stress_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    from python.scheduling_v3.pipeline import run_v3_pipeline

    return run_v3_pipeline(
        args.allocation_task_id,
        top_k=args.top_k,
        plan_count=args.plan_count,
        scheme_count=args.scheme_count,
        solver_time_limit_seconds=args.solver_time_limit_seconds,
        generation_mode=args.generation_mode,
        max_auto_stage=args.max_auto_stage,
        skip_diversity=args.skip_diversity,
        output_dir=args.output_dir,
    )


def inspect_output(summary_path: Path) -> dict[str, Any]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if payload.get("architecture") == "v3_auto_pipeline":
        return {
            "architecture": payload.get("architecture"),
            "best_stage": payload.get("best_stage"),
            "runtime_s": payload.get("runtime_s"),
            "max_auto_stage": payload.get("max_auto_stage"),
            "stages": [
                {
                    "stage": stage.get("stage"),
                    "status": stage.get("status"),
                    "runtime_s": stage.get("runtime_s"),
                    "scheme_count": stage.get("scheme_count"),
                    "solver_status": stage.get("solver_status"),
                    "output_dir": stage.get("output_dir"),
                }
                for stage in payload.get("stages") or []
            ],
        }
    return {
        "architecture": payload.get("architecture"),
        "generation_mode": payload.get("generation_mode"),
        "task_count": payload.get("task_count"),
        "runtime_s": payload.get("runtime_s"),
        "solver_status": payload.get("solver_status"),
        "scheme_count": payload.get("scheme_count"),
        "conflicts": payload.get("conflicts"),
        "output_dir": payload.get("output_dir"),
    }


def _fetch_teachers(conn) -> list[dict[str, Any]]:
    return _fetch_all(conn, "SELECT id, name FROM teacher WHERE status = 'ACTIVE' ORDER BY id")


def _fetch_class_groups(conn) -> list[dict[str, Any]]:
    return _fetch_all(conn, "SELECT id, name FROM class_group ORDER BY id")


def _fetch_professional_courses(conn) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT id, name, code, required_room_type
        FROM course
        WHERE status = 'ACTIVE'
          AND COALESCE(course_type, '') <> '实践课'
          AND required_room_type IS NOT NULL
        ORDER BY id
        """,
    )


def _fetch_all(conn, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def _limited(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    return rows[:limit] if limit and limit > 0 else rows


def _require_pool(name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No {name} found in DB; import base data before preparing stress tasks.")


def _balanced_rows(
    *,
    task_count: int,
    teachers: list[dict[str, Any]],
    class_groups: list[dict[str, Any]],
    courses: list[dict[str, Any]],
    total_hours: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(task_count):
        teacher = teachers[index % len(teachers)]
        class_group = class_groups[index % len(class_groups)]
        course = courses[index % len(courses)]
        rows.append({
            "course_id": int(course["id"]),
            "course_code": course.get("code"),
            "teacher_id": int(teacher["id"]),
            "teacher_name": teacher.get("name"),
            "class_group_id": int(class_group["id"]),
            "class_group_name": class_group.get("name"),
            "total_hours": total_hours,
            "required_room_type": course.get("required_room_type") or "普通教室",
        })
    return rows


def _distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "teacher": _counter_stats(Counter(row["teacher_id"] for row in rows)),
        "class_group": _counter_stats(Counter(row["class_group_id"] for row in rows)),
        "course": _counter_stats(Counter(row["course_id"] for row in rows)),
        "room_type": dict(Counter(row["required_room_type"] for row in rows)),
    }


def _counter_stats(counter: Counter) -> dict[str, Any]:
    values = list(counter.values())
    return {
        "distinct": len(counter),
        "min": min(values) if values else 0,
        "max": max(values) if values else 0,
        "avg": round(sum(values) / len(values), 2) if values else 0,
        "max_minus_min": (max(values) - min(values)) if values else 0,
        "top5": counter.most_common(5),
    }


def _find_allocation_task_id(cursor, name: str) -> int | None:
    cursor.execute("SELECT id FROM allocation_task WHERE name = %s", (name,))
    row = cursor.fetchone()
    return int(row["id"]) if row else None


def _delete_generated_allocation(cursor, allocation_task_id: int) -> None:
    cursor.execute(
        """
        SELECT tt.id
        FROM teaching_task tt
        JOIN allocation_task_teaching_task att ON att.teaching_task_id = tt.id
        WHERE att.allocation_task_id = %s
          AND tt.notes LIKE 'v3_balanced_stress%%'
        """,
        (allocation_task_id,),
    )
    teaching_task_ids = [int(row["id"]) for row in cursor.fetchall()]
    cursor.execute("DELETE FROM allocation_task WHERE id = %s", (allocation_task_id,))
    if teaching_task_ids:
        placeholders = ",".join(["%s"] * len(teaching_task_ids))
        cursor.execute(f"DELETE FROM teaching_task WHERE id IN ({placeholders})", tuple(teaching_task_ids))


def _insert_generation_config(
    cursor,
    allocation_task_id: int,
    args: argparse.Namespace,
    profile: StressProfile,
) -> None:
    cursor.execute(
        """
        INSERT INTO allocation_task_generation_config
            (task_id, allowed_weeks, allowed_weekdays, allowed_periods, scheme_count,
             placement_top_k, raw_plan_count, cp_plan_count, solver_time_limit_seconds,
             generation_mode)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            allocation_task_id,
            args.allowed_weeks,
            args.allowed_weekdays,
            args.allowed_periods,
            profile.scheme_count,
            profile.placement_top_k,
            profile.raw_plan_count,
            profile.cp_plan_count,
            profile.solver_time_limit_seconds,
            profile.generation_mode,
        ),
    )


def _insert_teaching_tasks(
    cursor,
    allocation_task_id: int,
    rows: list[dict[str, Any]],
) -> list[int]:
    teaching_task_ids: list[int] = []
    for ordinal, row in enumerate(rows, start=1):
        cursor.execute(
            """
            INSERT INTO teaching_task
                (course_id, primary_teacher_id, total_hours, required_room_type, notes, status)
            VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
            """,
            (
                row["course_id"],
                row["teacher_id"],
                row["total_hours"],
                row["required_room_type"],
                f"v3_balanced_stress generated ordinal={ordinal}",
            ),
        )
        teaching_task_id = int(cursor.lastrowid)
        teaching_task_ids.append(teaching_task_id)
        cursor.execute(
            """
            INSERT INTO teaching_task_class_group (teaching_task_id, class_group_id)
            VALUES (%s, %s)
            """,
            (teaching_task_id, row["class_group_id"]),
        )
        cursor.execute(
            """
            INSERT INTO allocation_task_teaching_task (allocation_task_id, teaching_task_id)
            VALUES (%s, %s)
            """,
            (allocation_task_id, teaching_task_id),
        )
    return teaching_task_ids


if __name__ == "__main__":
    raise SystemExit(main())
