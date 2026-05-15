"""Generate LightGBM training samples for Edu-Flow-AI scheduling.

Output:
    ../data/training_samples.csv

A single row represents:
    TeachingTask + candidate TimeSlot + candidate Classroom + current schedule state -> score
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import pymysql
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: pymysql. Run `cd server/ml && python3 -m venv .venv "
        "&& source .venv/bin/activate && pip install -r requirements.txt` first."
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT_DIR.parent
PROJECT_DIR = SERVER_DIR.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_PATH = DATA_DIR / "training_samples.csv"

DEFAULT_DB_URL = (
    "jdbc:mysql://localhost:3306/edu_flow_ai?useUnicode=true&characterEncoding=utf8"
    "&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false"
)
DEFAULT_DB_USERNAME = "root"
DEFAULT_DB_PASSWORD = ""

FIELDNAMES = [
    "sample_id",
    "teaching_task_id",
    "candidate_classroom_id",
    "candidate_time_slot_id",
    "course_type",
    "total_hours",
    "required_room_type",
    "class_group_count",
    "total_student_count",
    "teacher_department",
    "teacher_title",
    "teacher_max_weekly_hours",
    "room_capacity",
    "room_type",
    "room_building",
    "capacity_margin",
    "capacity_ratio",
    "week_number",
    "day_of_week",
    "period_index",
    "is_morning",
    "is_afternoon",
    "is_evening",
    "is_early_period",
    "is_late_period",
    "teacher_occupied_at_slot",
    "class_occupied_at_slot",
    "room_occupied_at_slot",
    "teacher_day_load",
    "class_day_load",
    "teacher_week_load",
    "class_week_load",
    "is_capacity_enough",
    "is_room_type_match",
    "has_teacher_conflict",
    "has_class_conflict",
    "has_room_conflict",
    "has_hard_conflict",
    "score",
    "reject_reason",
]


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str = "utf8mb4"


@dataclass(frozen=True)
class PseudoAssignment:
    task_id: int
    teacher_id: int
    class_group_ids: tuple[int, ...]
    classroom_id: int
    time_slot_id: int
    week_number: int
    day_of_week: int
    period_index: int


def load_env_files() -> None:
    for env_path in (PROJECT_DIR / ".env", SERVER_DIR / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_jdbc_mysql_url(url: str) -> tuple[str, int, str, dict[str, list[str]]]:
    if url.startswith("jdbc:"):
        url = url[len("jdbc:") :]
    parsed = urlparse(url)
    if parsed.scheme != "mysql":
        raise ValueError(f"Only jdbc:mysql URLs are supported, got: {parsed.scheme}")
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("Database name is missing from DB_URL")
    return parsed.hostname or "localhost", parsed.port or 3306, database, parse_qs(parsed.query)


def load_db_config() -> DbConfig:
    load_env_files()
    db_url = os.getenv("DB_URL", DEFAULT_DB_URL)
    host, port, database, query = parse_jdbc_mysql_url(db_url)
    charset = query.get("characterEncoding", ["utf8mb4"])[0]
    if charset.lower() == "utf8":
        charset = "utf8mb4"
    return DbConfig(
        host=host,
        port=port,
        database=database,
        user=os.getenv("DB_USERNAME", DEFAULT_DB_USERNAME),
        password=os.getenv("DB_PASSWORD", DEFAULT_DB_PASSWORD),
        charset=charset,
    )


def connect(config: DbConfig):
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset=config.charset,
        cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_all(connection, sql: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return list(cursor.fetchall())


def fetch_tasks(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT
            tt.id AS teaching_task_id,
            tt.primary_teacher_id AS teacher_id,
            tt.assistant_teacher_id,
            tt.classroom_id AS bound_classroom_id,
            tt.total_hours,
            tt.required_room_type,
            c.course_type,
            c.required_hours AS course_required_hours,
            t.department AS teacher_department,
            t.title AS teacher_title,
            t.max_weekly_hours AS teacher_max_weekly_hours,
            bound_cr.classroom_type AS bound_classroom_type,
            COUNT(cg.id) AS class_group_count,
            COALESCE(SUM(cg.student_count), 0) AS total_student_count,
            GROUP_CONCAT(cg.id ORDER BY cg.id) AS class_group_ids,
            GROUP_CONCAT(cg.major ORDER BY cg.id) AS class_group_majors,
            GROUP_CONCAT(cg.grade ORDER BY cg.id) AS class_group_grades
        FROM teaching_task tt
        JOIN course c ON c.id = tt.course_id
        JOIN teacher t ON t.id = tt.primary_teacher_id
        LEFT JOIN classroom bound_cr ON bound_cr.id = tt.classroom_id
        LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
        LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
        WHERE tt.status = 'ACTIVE'
        GROUP BY
            tt.id,
            tt.primary_teacher_id,
            tt.assistant_teacher_id,
            tt.classroom_id,
            tt.total_hours,
            tt.required_room_type,
            c.course_type,
            c.required_hours,
            t.department,
            t.title,
            t.max_weekly_hours,
            bound_cr.classroom_type
        ORDER BY tt.id
        """,
    )


def fetch_classrooms(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT id, name, building, capacity, classroom_type
        FROM classroom
        WHERE status = 'ACTIVE'
        ORDER BY id
        """,
    )


def fetch_time_slots(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT id, week_number, day_of_week, period_index, label
        FROM time_slot
        ORDER BY week_number, day_of_week, period_index
        """,
    )


def parse_id_tuple(raw_ids: str | None) -> tuple[int, ...]:
    if not raw_ids:
        return ()
    return tuple(int(value) for value in raw_ids.split(",") if value)


def effective_required_room_type(task: dict[str, Any]) -> str:
    return task.get("required_room_type") or task.get("bound_classroom_type") or "普通教室"


def periods_needed(task: dict[str, Any]) -> int:
    total_hours = int(task.get("total_hours") or 0)
    return max(1, total_hours // 2)


def build_pseudo_assignments(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
) -> list[PseudoAssignment]:
    """Build a deterministic pseudo schedule to create conflict/state features.

    The current database may not have official course assignments yet. This pseudo schedule gives
    the sample generator a realistic occupied-state baseline without changing application data.
    """
    classrooms_by_id = {int(room["id"]): room for room in classrooms}
    teacher_slot: set[tuple[int, int]] = set()
    class_slot: set[tuple[int, int]] = set()
    room_slot: set[tuple[int, int]] = set()
    assignments: list[PseudoAssignment] = []

    for task in tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        classroom_id = int(task.get("bound_classroom_id") or classrooms[0]["id"])
        if classroom_id not in classrooms_by_id:
            classroom_id = int(classrooms[0]["id"])

        assigned_count = 0
        for slot in time_slots:
            slot_id = int(slot["id"])
            teacher_key = (teacher_id, slot_id)
            room_key = (classroom_id, slot_id)
            class_keys = [(class_group_id, slot_id) for class_group_id in class_group_ids]
            if teacher_key in teacher_slot or room_key in room_slot:
                continue
            if any(class_key in class_slot for class_key in class_keys):
                continue

            teacher_slot.add(teacher_key)
            room_slot.add(room_key)
            for class_key in class_keys:
                class_slot.add(class_key)
            assignments.append(
                PseudoAssignment(
                    task_id=task_id,
                    teacher_id=teacher_id,
                    class_group_ids=class_group_ids,
                    classroom_id=classroom_id,
                    time_slot_id=slot_id,
                    week_number=int(slot["week_number"]),
                    day_of_week=int(slot["day_of_week"]),
                    period_index=int(slot["period_index"]),
                )
            )
            assigned_count += 1
            if assigned_count >= periods_needed(task):
                break

    return assignments


def build_occupied_indexes(assignments: list[PseudoAssignment]) -> dict[str, Any]:
    indexes: dict[str, Any] = {
        "teacher_slot": defaultdict(set),
        "class_slot": defaultdict(set),
        "room_slot": defaultdict(set),
        "teacher_day_load": defaultdict(int),
        "class_day_load": defaultdict(int),
        "room_day_load": defaultdict(int),
        "teacher_week_load": defaultdict(int),
        "class_week_load": defaultdict(int),
    }
    for assignment in assignments:
        slot_id = assignment.time_slot_id
        week_day = (assignment.week_number, assignment.day_of_week)
        teacher_day = (assignment.teacher_id, *week_day)
        room_day = (assignment.classroom_id, *week_day)
        teacher_week = (assignment.teacher_id, assignment.week_number)

        indexes["teacher_slot"][(assignment.teacher_id, slot_id)].add(assignment.task_id)
        indexes["room_slot"][(assignment.classroom_id, slot_id)].add(assignment.task_id)
        indexes["teacher_day_load"][teacher_day] += 1
        indexes["room_day_load"][room_day] += 1
        indexes["teacher_week_load"][teacher_week] += 1

        for class_group_id in assignment.class_group_ids:
            class_day = (class_group_id, *week_day)
            class_week = (class_group_id, assignment.week_number)
            indexes["class_slot"][(class_group_id, slot_id)].add(assignment.task_id)
            indexes["class_day_load"][class_day] += 1
            indexes["class_week_load"][class_week] += 1
    return indexes


def is_room_type_match(required_room_type: str, room_type: str | None) -> bool:
    if not required_room_type:
        return True
    if not room_type:
        return False
    return required_room_type == room_type or required_room_type in room_type or room_type in required_room_type


def score_sample(
    *,
    has_hard_conflict: bool,
    is_type_match: bool,
    capacity_ratio: float,
    is_early_period: int,
    is_late_period: int,
    teacher_day_load: int,
    class_day_load: int,
    teacher_week_load: int,
    teacher_max_weekly_hours: int | None,
) -> float:
    if has_hard_conflict:
        return 0.0

    score = 0.60
    if is_type_match:
        score += 0.10
    if 0.50 <= capacity_ratio <= 0.90:
        score += 0.10
    if not is_early_period and not is_late_period:
        score += 0.05
    if teacher_day_load <= 3:
        score += 0.05
    if class_day_load <= 3:
        score += 0.05
    if teacher_max_weekly_hours is None or teacher_week_load * 2 <= teacher_max_weekly_hours:
        score += 0.05
    return round(min(max(score, 0.0), 1.0), 4)


def reject_reason(*, teacher_conflict: bool, class_conflict: bool, room_conflict: bool, capacity_enough: bool, type_match: bool) -> str:
    reasons: list[str] = []
    if teacher_conflict:
        reasons.append("teacher_conflict")
    if class_conflict:
        reasons.append("class_conflict")
    if room_conflict:
        reasons.append("room_conflict")
    if not capacity_enough:
        reasons.append("capacity_not_enough")
    if not type_match:
        reasons.append("room_type_mismatch")
    return ";".join(reasons)


def generate_rows(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    max_rows: int | None,
) -> list[dict[str, Any]]:
    pseudo_assignments = build_pseudo_assignments(tasks, classrooms, time_slots)
    indexes = build_occupied_indexes(pseudo_assignments)
    rows: list[dict[str, Any]] = []
    sample_id = 1

    for task in tasks:
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        required_room_type = effective_required_room_type(task)
        total_student_count = int(task.get("total_student_count") or 0)
        teacher_max_weekly_hours = task.get("teacher_max_weekly_hours")

        for slot in time_slots:
            slot_id = int(slot["id"])
            week_number = int(slot["week_number"])
            day_of_week = int(slot["day_of_week"])
            period_index = int(slot["period_index"])
            is_morning = int(period_index in (1, 2))
            is_afternoon = int(period_index in (3, 4))
            is_evening = int(period_index >= 5)
            is_early_period = int(period_index == 1)
            is_late_period = int(period_index >= 5)

            teacher_slot_tasks = indexes["teacher_slot"][(teacher_id, slot_id)] - {task_id}
            class_slot_tasks: set[int] = set()
            for class_group_id in class_group_ids:
                class_slot_tasks.update(indexes["class_slot"][(class_group_id, slot_id)] - {task_id})

            teacher_occupied = bool(teacher_slot_tasks)
            class_occupied = bool(class_slot_tasks)
            teacher_day_load = indexes["teacher_day_load"][(teacher_id, week_number, day_of_week)]
            teacher_week_load = indexes["teacher_week_load"][(teacher_id, week_number)]
            class_day_load = max(
                [indexes["class_day_load"][(class_group_id, week_number, day_of_week)] for class_group_id in class_group_ids]
                or [0]
            )
            class_week_load = max(
                [indexes["class_week_load"][(class_group_id, week_number)] for class_group_id in class_group_ids]
                or [0]
            )

            for room in classrooms:
                room_id = int(room["id"])
                room_capacity = int(room.get("capacity") or 0)
                room_type = room.get("classroom_type") or ""
                room_slot_tasks = indexes["room_slot"][(room_id, slot_id)] - {task_id}
                room_occupied = bool(room_slot_tasks)
                capacity_margin = room_capacity - total_student_count
                capacity_ratio = round(total_student_count / room_capacity, 4) if room_capacity > 0 else 1.0
                capacity_enough = room_capacity >= total_student_count if room_capacity > 0 else False
                type_match = is_room_type_match(required_room_type, room_type)
                teacher_conflict = teacher_occupied
                class_conflict = class_occupied
                room_conflict = room_occupied
                has_hard_conflict = teacher_conflict or class_conflict or room_conflict or not capacity_enough or not type_match
                row_score = score_sample(
                    has_hard_conflict=has_hard_conflict,
                    is_type_match=type_match,
                    capacity_ratio=capacity_ratio,
                    is_early_period=is_early_period,
                    is_late_period=is_late_period,
                    teacher_day_load=teacher_day_load,
                    class_day_load=class_day_load,
                    teacher_week_load=teacher_week_load,
                    teacher_max_weekly_hours=int(teacher_max_weekly_hours) if teacher_max_weekly_hours is not None else None,
                )

                rows.append(
                    {
                        "sample_id": sample_id,
                        "teaching_task_id": task_id,
                        "candidate_classroom_id": room_id,
                        "candidate_time_slot_id": slot_id,
                        "course_type": task.get("course_type") or "",
                        "total_hours": int(task.get("total_hours") or 0),
                        "required_room_type": required_room_type,
                        "class_group_count": int(task.get("class_group_count") or 0),
                        "total_student_count": total_student_count,
                        "teacher_department": task.get("teacher_department") or "",
                        "teacher_title": task.get("teacher_title") or "",
                        "teacher_max_weekly_hours": teacher_max_weekly_hours or 0,
                        "room_capacity": room_capacity,
                        "room_type": room_type,
                        "room_building": room.get("building") or "",
                        "capacity_margin": capacity_margin,
                        "capacity_ratio": capacity_ratio,
                        "week_number": week_number,
                        "day_of_week": day_of_week,
                        "period_index": period_index,
                        "is_morning": is_morning,
                        "is_afternoon": is_afternoon,
                        "is_evening": is_evening,
                        "is_early_period": is_early_period,
                        "is_late_period": is_late_period,
                        "teacher_occupied_at_slot": int(teacher_occupied),
                        "class_occupied_at_slot": int(class_occupied),
                        "room_occupied_at_slot": int(room_occupied),
                        "teacher_day_load": teacher_day_load,
                        "class_day_load": class_day_load,
                        "teacher_week_load": teacher_week_load,
                        "class_week_load": class_week_load,
                        "is_capacity_enough": int(capacity_enough),
                        "is_room_type_match": int(type_match),
                        "has_teacher_conflict": int(teacher_conflict),
                        "has_class_conflict": int(class_conflict),
                        "has_room_conflict": int(room_conflict),
                        "has_hard_conflict": int(has_hard_conflict),
                        "score": row_score,
                        "reject_reason": reject_reason(
                            teacher_conflict=teacher_conflict,
                            class_conflict=class_conflict,
                            room_conflict=room_conflict,
                            capacity_enough=capacity_enough,
                            type_match=type_match,
                        ),
                    }
                )
                sample_id += 1
                if max_rows is not None and len(rows) >= max_rows:
                    return rows
    return rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LightGBM training samples for Edu-Flow-AI scheduling.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="CSV output path.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional maximum number of rows to generate.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)

    if not tasks:
        raise RuntimeError("No active teaching tasks found. Seed or create teaching tasks before generating samples.")
    if not classrooms:
        raise RuntimeError("No active classrooms found. Seed or create classrooms before generating samples.")
    if not time_slots:
        raise RuntimeError("No time slots found. Seed or create time slots before generating samples.")

    rows = generate_rows(tasks, classrooms, time_slots, args.max_rows)
    write_csv(rows, args.output)
    print(f"Generated {len(rows)} samples -> {args.output}")


if __name__ == "__main__":
    main()
