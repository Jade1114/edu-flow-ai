"""Build room-ranker training samples from real timetables.

Positive samples are rooms actually used by a teaching task.
Negative samples are feasible alternative rooms for the same task.
No day/period/template features are included; this dataset trains only:

    teaching_task + classroom -> room rank score
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from python.scheduling_v2.room_ranker import ROOM_RANK_FEATURES

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT = DATA / "room_ranker_samples.csv"
METADATA_FIELDS = [
    "label",
    "course_code",
    "class_group",
    "room_name",
    "sample_type",
]
FIELDS = METADATA_FIELDS + ROOM_RANK_FEATURES


def build() -> Path:
    print("加载真实排课 JSONL...")
    timetables = _read_jsonl(DATA / "timetables.jsonl")
    tasks = _read_jsonl(DATA / "teaching_tasks.jsonl")
    courses = {str(row.get("code") or ""): row for row in _read_jsonl(DATA / "courses.jsonl")}
    classrooms = _read_jsonl(DATA / "classrooms.jsonl")
    class_groups = {str(row.get("name") or ""): row for row in _read_jsonl(DATA / "class_groups.jsonl")}
    teachers = _read_jsonl(DATA / "teachers.jsonl")
    teacher_map = {
        str(entry.get("name") or ""): {"departments": entry.get("departments", [])}
        for entry in teachers
    }

    task_map = {
        (str(row.get("course_code") or ""), str(row.get("class_group") or "")): row
        for row in tasks
    }
    used_rooms: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for entry in timetables:
        key = (str(entry.get("course_code") or ""), str(entry.get("class_group") or ""))
        room_name = str(entry.get("room") or "")
        if key in task_map and room_name:
            used_rooms[key][room_name] += 1

    rng = random.Random(42)
    samples: list[dict[str, Any]] = []
    for key, room_counts in used_rooms.items():
        task = task_map.get(key)
        if not task:
            continue
        course = courses.get(key[0], {})
        class_group = class_groups.get(key[1], {})
        positive_rooms = set(room_counts)
        feasible_rooms = [
            room for room in classrooms
            if _is_feasible(task, course, class_group, room)
        ]
        if not feasible_rooms:
            continue

        for room_name in positive_rooms:
            room = next((item for item in classrooms if str(item.get("name") or "") == room_name), None)
            if not room:
                continue
            samples.append(_make_sample(1, "actual", task, course, class_group, room, teacher_map))

        negatives = [room for room in feasible_rooms if str(room.get("name") or "") not in positive_rooms]
        rng.shuffle(negatives)
        for room in negatives[: max(4, min(12, len(positive_rooms) * 6))]:
            samples.append(_make_sample(0, "alternative", task, course, class_group, room, teacher_map))

    print(f"样本数: {len(samples)}")
    print(f"正样本: {sum(1 for row in samples if row['label'] == 1)}")
    print(f"负样本: {sum(1 for row in samples if row['label'] == 0)}")

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(samples)
    print(f"输出: {OUTPUT}")
    return OUTPUT


def _make_sample(
    label: int,
    sample_type: str,
    task: dict[str, Any],
    course: dict[str, Any],
    class_group: dict[str, Any],
    room: dict[str, Any],
    teacher_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    student_count = int(class_group.get("student_count") or 0)
    capacity = int(room.get("capacity") or 0)
    required_type = _resolve_training_required_type(course, task)
    room_type = _norm(room.get("classroom_type") or "")
    total_hours = float(task.get("total_hours") or course.get("hours") or 0)

    # Teacher department lookup
    teacher_name = str(task.get("teacher") or "")
    teacher_info = (teacher_map or {}).get(teacher_name, {})
    departments = teacher_info.get("departments", [])
    teacher_dept = str(departments[0]).strip().lower() if departments else teacher_name.lower()

    # Class group major
    class_major = str(class_group.get("major") or "").strip().lower()

    row = {
        "label": label,
        "course_code": str(task.get("course_code") or ""),
        "class_group": str(task.get("class_group") or ""),
        "room_name": str(room.get("name") or ""),
        "sample_type": sample_type,
        "student_count": float(student_count),
        "total_hours": total_hours,
        "total_lessons": total_hours / 2.0,
        "room_capacity": float(capacity),
        "capacity_margin": float(capacity - student_count),
        "capacity_ratio": float(student_count / max(1, capacity)),
        "required_type_match": 1.0 if required_type and required_type == room_type else 0.0,
        "course_type_code": float(_stable_code(course.get("course_type"))),
        "required_room_type_code": float(_stable_code(required_type)),
        "room_type_code": float(_stable_code(room_type)),
        "building_code": float(_building_code(room.get("name"))),
        "teacher_department_code": float(_stable_code(teacher_dept)),
        "class_group_major_code": float(_stable_code(class_major)),
        "course_code_code": float(_stable_code(str(task.get("course_code") or ""))),
        "class_group_name_code": float(_stable_code(str(task.get("class_group") or ""))),
    }
    return row


def _is_feasible(
    task: dict[str, Any],
    course: dict[str, Any],
    class_group: dict[str, Any],
    room: dict[str, Any],
) -> bool:
    capacity = int(room.get("capacity") or 0)
    student_count = int(class_group.get("student_count") or 0)
    if capacity < student_count:
        return False
    required_type = _resolve_training_required_type(course, task)
    room_type = _norm(room.get("classroom_type") or "")
    if not room_type:
        return False
    return required_type == room_type


def _resolve_training_required_type(course: dict[str, Any], task: dict[str, Any]) -> str:
    """Resolve required classroom type from course data, with course_type fallback."""
    explicit = _norm(course.get("required_room_type") or "")
    if explicit:
        return explicit
    # Infer from course_type
    course_type = _norm(str(task.get("course_type") or course.get("course_type") or ""))
    type_map = {
        "理论课": "普通教室",
        "上机课": "机房",
        "实践课": "普通教室",
        "体育课": "操场",
    }
    return type_map.get(course_type, "")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _norm(value: Any) -> str:
    raw = str(value or "").strip().lower()
    replacements = {
        "计算机房": "机房",
        "电脑室": "机房",
        "多媒体教室": "普通教室",
        "阶梯教室": "普通教室",
        "教室": "普通教室",
    }
    return replacements.get(raw, raw)


def _stable_code(value: Any, modulo: int = 997) -> int:
    text = _norm(value)
    if not text:
        return 0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return total + 1


def _building_code(value: Any) -> int:
    text = str(value or "").strip()
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return int(digits[:4])
    return _stable_code(text, modulo=97)


if __name__ == "__main__":
    build()
