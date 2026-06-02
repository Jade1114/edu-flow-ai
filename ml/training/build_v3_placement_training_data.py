"""Build V3 placement-model training samples from real timetable JSONL files.

Target contract:
  input  = course_name + teacher_no + teacher_name + class_name
  output = day_of_week + period_index + classroom

The generated CSV intentionally keeps human-readable identity columns first so
we can audit alignment before training a new model.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT_PATH = DATA_DIR / "v3_placement_training_samples.csv"
DAY_PERIODS = [(day, period) for day in range(1, 6) for period in range(1, 6)]
DEFAULT_NEGATIVES_PER_POSITIVE = 4
ALLOWED_COURSE_TYPES = frozenset({"理论课", "上机课"})
ALLOWED_CLASSROOM_TYPES = frozenset({"普通教室", "机房"})

FIELDS = [
    "label",
    "sample_type",
    "course_name",
    "course_code",
    "teacher_no",
    "teacher_no_source",
    "teacher_name",
    "class_name",
    "class_major",
    "class_department",
    "class_grade",
    "class_no",
    "student_count",
    "total_hours",
    "course_type",
    "required_room_type",
    "day_of_week",
    "period_index",
    "classroom_name",
    "classroom_type",
    "classroom_capacity",
    "capacity_margin",
    "capacity_ratio",
    "is_room_type_match",
    "source_week",
    "source_period_label",
    "source_key",
]


def build(
    *,
    data_dir: Path = DATA_DIR,
    output_path: Path = OUTPUT_PATH,
    negatives_per_positive: int = DEFAULT_NEGATIVES_PER_POSITIVE,
    seed: int = 42,
) -> Path:
    courses = _by_key(_read_jsonl(data_dir / "courses.jsonl"), "code")
    teachers = _by_key(_read_jsonl(data_dir / "teachers.jsonl"), "name")
    class_groups = _by_key(_read_jsonl(data_dir / "class_groups.jsonl"), "name")
    classrooms = _by_key(_read_jsonl(data_dir / "classrooms.jsonl"), "name")
    teaching_tasks = _index_teaching_tasks(_read_jsonl(data_dir / "teaching_tasks.jsonl"))
    timetables = _read_jsonl(data_dir / "timetables.jsonl")

    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    skip_counts: Counter[str] = Counter()
    room_pool_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for timetable in timetables:
        source = _resolve_source(
            timetable,
            teaching_tasks,
            courses,
            teachers,
            class_groups,
            classrooms,
        )
        if source is None:
            skip_counts["unresolved_positive"] += 1
            continue
        if not _is_supported_course(source["course"]):
            skip_counts["unsupported_course_type"] += 1
            continue
        if not _is_supported_classroom(source["classroom"]):
            skip_counts["unsupported_classroom_type"] += 1
            continue
        positive = _make_row(1, "actual", source, timetable)
        rows.append(positive)

        room_pool = _cached_room_pool(source, classrooms, room_pool_cache)
        positive_resource = (
            positive["classroom_name"],
            positive["day_of_week"],
            positive["period_index"],
        )
        added = 0
        attempts = 0
        max_attempts = max(50, negatives_per_positive * 20)
        while added < negatives_per_positive and attempts < max_attempts and room_pool:
            attempts += 1
            classroom = rng.choice(room_pool)
            day, period = rng.choice(DAY_PERIODS)
            if (classroom.get("name"), day, period) == positive_resource:
                continue
            rows.append(_make_row(
                0,
                "alternative",
                {
                    **source,
                    "classroom": classroom,
                    "day_of_week": day,
                    "period_index": period,
                },
                timetable,
            ))
            added += 1
        if added == 0:
            skip_counts["no_negative_candidates"] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"输出: {output_path}")
    print(f"样本数: {len(rows)}")
    print(f"正样本: {sum(1 for row in rows if row['label'] == 1)}")
    print(f"负样本: {sum(1 for row in rows if row['label'] == 0)}")
    print(f"跳过统计: {dict(skip_counts)}")
    return output_path


def _resolve_source(
    timetable: dict[str, Any],
    teaching_tasks: dict[tuple[str, str], dict[str, Any]],
    courses: dict[str, dict[str, Any]],
    teachers: dict[str, dict[str, Any]],
    class_groups: dict[str, dict[str, Any]],
    classrooms: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    course_code = str(timetable.get("course_code") or "").strip()
    class_name = str(timetable.get("class_group") or "").strip()
    room_name = str(timetable.get("room") or "").strip()
    task = teaching_tasks.get((course_code, class_name))
    course = courses.get(course_code)
    class_group = class_groups.get(class_name)
    classroom = classrooms.get(room_name)
    if not task or not course or not class_group or not classroom:
        return None
    teacher_name = str(task.get("teacher") or "").strip()
    teacher = teachers.get(teacher_name) or {}
    day = _safe_int(timetable.get("day"))
    period = _safe_int(timetable.get("period_start"))
    if day < 1 or day > 7 or period < 1 or period > 5:
        return None
    teacher_no, teacher_no_source = _teacher_no(teacher_name, teacher)
    return {
        "task": task,
        "course": course,
        "teacher": teacher,
        "teacher_no": teacher_no,
        "teacher_no_source": teacher_no_source,
        "teacher_name": teacher_name,
        "class_group": class_group,
        "class_name": class_name,
        "classroom": classroom,
        "day_of_week": day,
        "period_index": period,
        "source_key": f"{course_code}|{teacher_name}|{class_name}",
    }


def _make_row(
    label: int,
    sample_type: str,
    source: dict[str, Any],
    timetable: dict[str, Any],
) -> dict[str, Any]:
    course = source["course"]
    task = source["task"]
    class_group = source["class_group"]
    classroom = source["classroom"]
    student_count = _safe_int(class_group.get("student_count"))
    capacity = _safe_int(classroom.get("capacity"))
    required_room_type = _required_room_type(course, task)
    classroom_type = str(classroom.get("classroom_type") or "")
    capacity_margin = capacity - student_count
    return {
        "label": label,
        "sample_type": sample_type,
        "course_name": str(course.get("name") or ""),
        "course_code": str(course.get("code") or task.get("course_code") or ""),
        "teacher_no": source["teacher_no"],
        "teacher_no_source": source["teacher_no_source"],
        "teacher_name": source["teacher_name"],
        "class_name": source["class_name"],
        "class_major": str(class_group.get("major") or ""),
        "class_department": str(class_group.get("department") or ""),
        "class_grade": str(class_group.get("grade") or ""),
        "class_no": _extract_class_no(source["class_name"]),
        "student_count": student_count,
        "total_hours": float(task.get("total_hours") or course.get("hours") or 0),
        "course_type": str(course.get("course_type") or ""),
        "required_room_type": required_room_type,
        "day_of_week": source["day_of_week"],
        "period_index": source["period_index"],
        "classroom_name": str(classroom.get("name") or ""),
        "classroom_type": classroom_type,
        "classroom_capacity": capacity,
        "capacity_margin": capacity_margin,
        "capacity_ratio": round(student_count / max(1, capacity), 6),
        "is_room_type_match": int(_norm(required_room_type) == _norm(classroom_type)) if required_room_type else 0,
        "source_week": _safe_int(timetable.get("week")),
        "source_period_label": str(timetable.get("period_label") or ""),
        "source_key": source["source_key"],
    }


def _cached_room_pool(
    source: dict[str, Any],
    classrooms: dict[str, dict[str, Any]],
    cache: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    key = (
        str(source["course"].get("code") or source["task"].get("course_code") or ""),
        source["class_name"],
    )
    if key in cache:
        return cache[key]
    source_classroom = source["classroom"]
    candidate_rooms = [room for room in classrooms.values() if _room_feasible(source, room)]
    if source_classroom not in candidate_rooms:
        candidate_rooms.append(source_classroom)
    cache[key] = candidate_rooms
    return candidate_rooms


def _room_feasible(source: dict[str, Any], room: dict[str, Any]) -> bool:
    if not _is_supported_classroom(room):
        return False
    class_group = source["class_group"]
    course = source["course"]
    task = source["task"]
    student_count = _safe_int(class_group.get("student_count"))
    capacity = _safe_int(room.get("capacity"))
    if capacity > 0 and student_count > capacity:
        return False
    required = _norm(_required_room_type(course, task))
    room_type = _norm(room.get("classroom_type"))
    return not required or required == room_type


def _is_supported_course(course: dict[str, Any]) -> bool:
    return str(course.get("course_type") or "").strip() in ALLOWED_COURSE_TYPES


def _is_supported_classroom(classroom: dict[str, Any]) -> bool:
    room_type = str(classroom.get("classroom_type") or "").strip()
    name = str(classroom.get("name") or "").strip().lower()
    if room_type not in ALLOWED_CLASSROOM_TYPES:
        return False
    if name.startswith("xn") or name.startswith("虚拟"):
        return False
    return "操场" not in name and "体育" not in name


def _index_teaching_tasks(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        key = (
            str(row.get("course_code") or "").strip(),
            str(row.get("class_group") or "").strip(),
        )
        if key in index:
            duplicate_counts[key] += 1
            continue
        index[key] = row
    if duplicate_counts:
        print(f"教学任务重复键: {len(duplicate_counts)} 个，保留第一条")
    return index


def _required_room_type(course: dict[str, Any], task: dict[str, Any]) -> str:
    explicit = str(course.get("required_room_type") or task.get("required_room_type") or "").strip()
    if explicit:
        return explicit
    type_map = {
        "理论课": "普通教室",
        "上机课": "机房",
        "实践课": "普通教室",
    }
    return type_map.get(str(course.get("course_type") or "").strip(), "")


def _teacher_no(teacher_name: str, teacher: dict[str, Any]) -> tuple[str, str]:
    for key in ("teacher_no", "employee_no", "employeeNo"):
        value = str(teacher.get(key) or "").strip()
        if value:
            return value, key
    return f"TEACHER_{teacher_name}", "generated"


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or "").strip(): row for row in rows if str(row.get(key) or "").strip()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _extract_class_no(value: str) -> int:
    if "班" not in value:
        return 0
    before = value.split("班")[0]
    digits = ""
    for char in reversed(before):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return int(digits) if digits else 0


def _norm(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "")
    replacements = {
        "计算机房": "机房",
        "电脑室": "机房",
        "多媒体教室": "普通教室",
        "阶梯教室": "普通教室",
        "教室": "普通教室",
    }
    return replacements.get(raw, raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V3 placement training samples.")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--negatives-per-positive", type=int, default=DEFAULT_NEGATIVES_PER_POSITIVE)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    build(
        data_dir=Path(args.data_dir),
        output_path=Path(args.output),
        negatives_per_positive=max(0, args.negatives_per_positive),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
