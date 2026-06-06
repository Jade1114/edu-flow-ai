#!/usr/bin/env python3
"""Diagnose oversized/public-course-like teaching tasks before CP-SAT scheduling."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from python.db.config import connect, load_db_config  # noqa: E402


@dataclass(frozen=True)
class Thresholds:
    public_course_task_count: int
    public_course_class_count: int
    public_course_teacher_count: int
    teacher_course_task_count: int
    teacher_course_class_count: int
    high_task_hours: int
    high_task_class_count: int
    high_task_student_count: int


@dataclass
class CourseSummary:
    course_id: int
    course_code: str
    course_name: str
    course_type: str
    required_room_type: str
    task_count: int
    teacher_count: int
    class_group_count: int
    total_hours: int
    max_task_hours: int
    high_hour_task_count: int
    total_sessions: int
    total_students: int
    max_teacher_task_count: int
    max_teacher_class_count: int
    anomaly_score: int
    reasons: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find public-course-like / oversized teaching tasks that may overload CP-SAT."
    )
    parser.add_argument("--allocation-task-id", type=int, help="Only analyze teaching tasks selected by this allocation task.")
    parser.add_argument("--status", default="ACTIVE", help="Teaching task status filter. Default: ACTIVE")
    parser.add_argument("--public-course-task-count", type=int, default=20)
    parser.add_argument("--public-course-class-count", type=int, default=20)
    parser.add_argument("--public-course-teacher-count", type=int, default=5)
    parser.add_argument("--teacher-course-task-count", type=int, default=5)
    parser.add_argument("--teacher-course-class-count", type=int, default=5)
    parser.add_argument("--high-task-hours", type=int, default=80)
    parser.add_argument("--high-task-class-count", type=int, default=2)
    parser.add_argument("--high-task-student-count", type=int, default=120)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--format", choices=("text", "json", "jsonl", "csv"), default="text")
    parser.add_argument("--output", type=Path, help="Optional output path.")
    return parser.parse_args()


def fetch_rows(allocation_task_id: int | None, status: str) -> list[dict[str, Any]]:
    params: list[Any] = [status]
    allocation_join = ""
    allocation_filter = ""
    if allocation_task_id is not None:
        allocation_join = "JOIN allocation_task_teaching_task attt ON attt.teaching_task_id = tt.id"
        allocation_filter = "AND attt.allocation_task_id = %s"
        params.append(allocation_task_id)

    sql = f"""
        SELECT
            tt.id AS teaching_task_id,
            tt.course_id,
            c.code AS course_code,
            c.name AS course_name,
            c.course_type,
            c.required_room_type AS course_required_room_type,
            tt.primary_teacher_id AS teacher_id,
            t.name AS teacher_name,
            tt.total_hours,
            tt.required_room_type AS task_required_room_type,
            COUNT(DISTINCT cg.id) AS class_group_count,
            COALESCE(SUM(DISTINCT cg.student_count), 0) AS total_student_count,
            GROUP_CONCAT(DISTINCT cg.id ORDER BY cg.id) AS class_group_ids,
            GROUP_CONCAT(DISTINCT cg.name ORDER BY cg.id SEPARATOR ' / ') AS class_group_names,
            GROUP_CONCAT(DISTINCT cg.major ORDER BY cg.major SEPARATOR ' / ') AS class_group_majors
        FROM teaching_task tt
        JOIN course c ON c.id = tt.course_id
        JOIN teacher t ON t.id = tt.primary_teacher_id
        {allocation_join}
        LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
        LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
        WHERE tt.status = %s
        {allocation_filter}
        GROUP BY
            tt.id, tt.course_id, c.code, c.name, c.course_type, c.required_room_type,
            tt.primary_teacher_id, t.name, tt.total_hours, tt.required_room_type
        ORDER BY tt.id
    """
    with connect(load_db_config()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return list(cursor.fetchall())


def split_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    return {int(part) for part in raw.split(",") if part.strip()}


def sessions_from_hours(hours: Any) -> int:
    return int(math.ceil(float(hours or 0) / 2.0))


def build_course_summaries(rows: list[dict[str, Any]], thresholds: Thresholds) -> list[CourseSummary]:
    by_course: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_course[int(row["course_id"] or 0)].append(row)

    summaries: list[CourseSummary] = []
    for course_id, course_rows in by_course.items():
        teacher_ids = {int(row["teacher_id"] or 0) for row in course_rows}
        class_ids: set[int] = set()
        room_types: set[str] = set()
        teacher_task_counts: Counter[int] = Counter()
        teacher_class_ids: dict[int, set[int]] = defaultdict(set)
        total_students = 0
        total_hours = 0
        total_sessions = 0
        max_task_hours = 0
        high_hour_task_count = 0

        for row in course_rows:
            teacher_id = int(row["teacher_id"] or 0)
            task_hours = int(row.get("total_hours") or 0)
            row_class_ids = split_ids(row.get("class_group_ids"))
            class_ids.update(row_class_ids)
            teacher_task_counts[teacher_id] += 1
            teacher_class_ids[teacher_id].update(row_class_ids)
            total_students += int(row.get("total_student_count") or 0)
            total_hours += task_hours
            total_sessions += sessions_from_hours(task_hours)
            max_task_hours = max(max_task_hours, task_hours)
            if task_hours >= thresholds.high_task_hours:
                high_hour_task_count += 1
            room_type = row.get("course_required_room_type") or row.get("task_required_room_type") or ""
            if room_type:
                room_types.add(str(room_type))

        max_teacher_task_count = max(teacher_task_counts.values(), default=0)
        max_teacher_class_count = max((len(ids) for ids in teacher_class_ids.values()), default=0)
        task_count = len(course_rows)
        teacher_count = len(teacher_ids)
        class_group_count = len(class_ids)
        reasons: list[str] = []

        if task_count >= thresholds.public_course_task_count:
            reasons.append(f"课程任务数高({task_count})")
        if class_group_count >= thresholds.public_course_class_count:
            reasons.append(f"覆盖班级多({class_group_count})")
        if teacher_count >= thresholds.public_course_teacher_count:
            reasons.append(f"参与教师多({teacher_count})")
        if max_teacher_task_count >= thresholds.teacher_course_task_count:
            reasons.append(f"单教师同课程任务多({max_teacher_task_count})")
        if max_teacher_class_count >= thresholds.teacher_course_class_count:
            reasons.append(f"单教师同课程覆盖班级多({max_teacher_class_count})")
        if max_task_hours >= thresholds.high_task_hours:
            reasons.append(f"课时太高(单任务最高{max_task_hours}, {high_hour_task_count}个任务>={thresholds.high_task_hours})")

        anomaly_score = sum([
            task_count >= thresholds.public_course_task_count,
            class_group_count >= thresholds.public_course_class_count,
            teacher_count >= thresholds.public_course_teacher_count,
            max_teacher_task_count >= thresholds.teacher_course_task_count,
            max_teacher_class_count >= thresholds.teacher_course_class_count,
            max_task_hours >= thresholds.high_task_hours,
        ])

        if anomaly_score > 0:
            first = course_rows[0]
            summaries.append(CourseSummary(
                course_id=course_id,
                course_code=str(first.get("course_code") or ""),
                course_name=str(first.get("course_name") or ""),
                course_type=str(first.get("course_type") or ""),
                required_room_type=" / ".join(sorted(room_types)),
                task_count=task_count,
                teacher_count=teacher_count,
                class_group_count=class_group_count,
                total_hours=total_hours,
                max_task_hours=max_task_hours,
                high_hour_task_count=high_hour_task_count,
                total_sessions=total_sessions,
                total_students=total_students,
                max_teacher_task_count=max_teacher_task_count,
                max_teacher_class_count=max_teacher_class_count,
                anomaly_score=anomaly_score,
                reasons=reasons,
            ))

    return sorted(summaries, key=lambda item: (-item.anomaly_score, -item.task_count, -item.class_group_count, item.course_id))


def build_teacher_course_anomalies(rows: list[dict[str, Any]], thresholds: Thresholds) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(int(row["teacher_id"] or 0), int(row["course_id"] or 0))].append(row)

    anomalies: list[dict[str, Any]] = []
    for (teacher_id, course_id), group_rows in groups.items():
        class_ids: set[int] = set()
        for row in group_rows:
            class_ids.update(split_ids(row.get("class_group_ids")))
        if len(group_rows) < thresholds.teacher_course_task_count and len(class_ids) < thresholds.teacher_course_class_count:
            continue
        first = group_rows[0]
        anomalies.append({
            "teacher_id": teacher_id,
            "teacher_name": first.get("teacher_name") or "",
            "course_id": course_id,
            "course_code": first.get("course_code") or "",
            "course_name": first.get("course_name") or "",
            "task_count": len(group_rows),
            "class_group_count": len(class_ids),
            "total_hours": sum(int(row.get("total_hours") or 0) for row in group_rows),
            "total_sessions": sum(sessions_from_hours(row.get("total_hours")) for row in group_rows),
            "teaching_task_ids": [int(row["teaching_task_id"]) for row in group_rows],
        })
    return sorted(anomalies, key=lambda item: (-item["task_count"], -item["class_group_count"], item["teacher_id"]))


def build_large_task_anomalies(rows: list[dict[str, Any]], thresholds: Thresholds) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for row in rows:
        total_hours = int(row.get("total_hours") or 0)
        class_group_count = int(row.get("class_group_count") or 0)
        total_student_count = int(row.get("total_student_count") or 0)
        reasons: list[str] = []
        if total_hours >= thresholds.high_task_hours:
            reasons.append(f"课时高({total_hours})")
        if class_group_count >= thresholds.high_task_class_count:
            reasons.append(f"合班数高({class_group_count})")
        if total_student_count >= thresholds.high_task_student_count:
            reasons.append(f"学生数高({total_student_count})")
        if reasons:
            anomalies.append({
                "teaching_task_id": int(row["teaching_task_id"]),
                "course_code": row.get("course_code") or "",
                "course_name": row.get("course_name") or "",
                "teacher_id": int(row.get("teacher_id") or 0),
                "teacher_name": row.get("teacher_name") or "",
                "total_hours": total_hours,
                "total_sessions": sessions_from_hours(total_hours),
                "class_group_count": class_group_count,
                "total_student_count": total_student_count,
                "class_group_names": row.get("class_group_names") or "",
                "reasons": reasons,
            })
    return sorted(anomalies, key=lambda item: (-len(item["reasons"]), -item["total_hours"], -item["class_group_count"]))


def build_payload(rows: list[dict[str, Any]], thresholds: Thresholds, top: int) -> dict[str, Any]:
    course_anomalies = build_course_summaries(rows, thresholds)
    excluded_course_ids = {item.course_id for item in course_anomalies if item.anomaly_score >= 2}
    suggested_excluded_task_ids = sorted({
        int(row["teaching_task_id"])
        for row in rows
        if int(row["course_id"] or 0) in excluded_course_ids
    })
    professional_candidate_task_ids = sorted({int(row["teaching_task_id"]) for row in rows} - set(suggested_excluded_task_ids))

    return {
        "summary": {
            "task_count": len(rows),
            "course_count": len({int(row["course_id"] or 0) for row in rows}),
            "teacher_count": len({int(row["teacher_id"] or 0) for row in rows}),
            "suggested_excluded_course_count": len(excluded_course_ids),
            "suggested_excluded_task_count": len(suggested_excluded_task_ids),
            "professional_candidate_task_count": len(professional_candidate_task_ids),
        },
        "thresholds": asdict(thresholds),
        "course_anomalies": [asdict(item) for item in course_anomalies[:top]],
        "suggested_excluded_course_ids": sorted(excluded_course_ids),
        "suggested_excluded_task_ids": suggested_excluded_task_ids,
        "professional_candidate_task_ids": professional_candidate_task_ids,
    }


def normalize_course_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload["course_anomalies"]:
        rows.append({
            "course_code": item["course_code"],
            "course_name": item["course_name"],
            "course_type": item["course_type"],
            "required_room_type": item["required_room_type"],
            "total_hours": item["total_hours"],
            "max_task_hours": item["max_task_hours"],
            "task_count": item["task_count"],
            "teacher_count": item["teacher_count"],
            "class_group_count": item["class_group_count"],
            "reasons": "；".join(item["reasons"]),
        })
    return rows


def render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Teaching Task Course Anomaly Report",
        "",
        "## Summary",
        f"- tasks: {summary['task_count']}",
        f"- courses: {summary['course_count']}",
        f"- teachers: {summary['teacher_count']}",
        f"- suggested excluded courses: {summary['suggested_excluded_course_count']}",
        f"- suggested excluded tasks: {summary['suggested_excluded_task_count']}",
        f"- professional candidate tasks: {summary['professional_candidate_task_count']}",
        "",
        "## Course Anomalies",
    ]
    for item in normalize_course_rows(payload):
        lines.append(
            f"- {item['course_code']} {item['course_name']} | type={item['course_type']} "
            f"room={item['required_room_type'] or '-'} hours={item['total_hours']} "
            f"tasks={item['task_count']} teachers={item['teacher_count']} classes={item['class_group_count']} | "
            f"{item['reasons']}"
        )
    return "\n".join(lines) + "\n"


def render_jsonl(payload: dict[str, Any]) -> str:
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in normalize_course_rows(payload)) + "\n"


def render_csv(payload: dict[str, Any]) -> str:
    import io

    rows = normalize_course_rows(payload)
    fieldnames = [
        "course_code",
        "course_name",
        "course_type",
        "required_room_type",
        "total_hours",
        "max_task_hours",
        "task_count",
        "teacher_count",
        "class_group_count",
        "reasons",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> None:
    args = parse_args()
    thresholds = Thresholds(
        public_course_task_count=args.public_course_task_count,
        public_course_class_count=args.public_course_class_count,
        public_course_teacher_count=args.public_course_teacher_count,
        teacher_course_task_count=args.teacher_course_task_count,
        teacher_course_class_count=args.teacher_course_class_count,
        high_task_hours=args.high_task_hours,
        high_task_class_count=args.high_task_class_count,
        high_task_student_count=args.high_task_student_count,
    )
    rows = fetch_rows(args.allocation_task_id, args.status)
    payload = build_payload(rows, thresholds, args.top)

    if args.format == "json":
        output = json.dumps(payload, ensure_ascii=False, indent=2)
    elif args.format == "jsonl":
        output = render_jsonl(payload)
    elif args.format == "csv":
        output = render_csv(payload)
    else:
        output = render_text(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
