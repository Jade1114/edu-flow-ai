"""Build placement-ranker samples from real timetables.

Positive samples are actual historical (room, day, period) placements.
Negative samples are feasible but unused alternatives for the same task.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ml.scheduling_v2.placement_ranker import PLACEMENT_RANK_FEATURES

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT = DATA / "placement_ranker_samples.csv"
STATS_OUTPUT = DATA / "placement_ranker_stats.json"
DAY_PERIODS = [(day, period) for day in range(1, 8) for period in range(1, 6)]
METADATA_FIELDS = [
    "label",
    "course_code",
    "teacher",
    "class_group",
    "room_name",
    "day",
    "period",
    "sample_type",
]
FIELDS = METADATA_FIELDS + PLACEMENT_RANK_FEATURES


def build() -> Path:
    print("加载 placement ranker 训练数据源...")
    timetables = _read_jsonl(DATA / "timetables.jsonl")
    tasks = _read_jsonl(DATA / "teaching_tasks.jsonl")
    courses = {str(row.get("code") or ""): row for row in _read_jsonl(DATA / "courses.jsonl")}
    classrooms = _read_jsonl(DATA / "classrooms.jsonl")
    class_groups = {str(row.get("name") or ""): row for row in _read_jsonl(DATA / "class_groups.jsonl")}
    teacher_map = {
        str(entry.get("name") or ""): {"departments": entry.get("departments", [])}
        for entry in _read_jsonl(DATA / "teachers.jsonl")
    }

    task_map = {
        (str(row.get("course_code") or ""), str(row.get("class_group") or "")): row
        for row in tasks
    }
    room_map = {str(room.get("name") or ""): room for room in classrooms}
    used: dict[tuple[str, str], Counter[tuple[str, int, int]]] = defaultdict(Counter)
    skip_counts: Counter[str] = Counter()
    for row in timetables:
        key = (str(row.get("course_code") or ""), str(row.get("class_group") or ""))
        if key not in task_map:
            skip_counts["missing_task"] += 1
            continue
        room = str(row.get("room") or "")
        day = _safe_int(row.get("day"))
        period = _period_start_to_index(row.get("period_start"))
        if not room or day < 1 or day > 7 or period < 1 or period > 5:
            skip_counts["invalid_placement"] += 1
            continue
        used[key][(room, day, period)] += 1

    stats = _build_frequency_stats(used, task_map, class_groups, teacher_map)
    rng = random.Random(42)
    samples: list[dict[str, Any]] = []

    for key, placement_counts in used.items():
        task = task_map.get(key)
        course = courses.get(key[0], {})
        class_group = class_groups.get(key[1], {})
        if not task or not course or not class_group:
            skip_counts["missing_metadata"] += 1
            continue
        feasible_rooms = [
            room for room in classrooms
            if _is_feasible(task, course, class_group, room)
        ]
        if not feasible_rooms:
            skip_counts["no_feasible_rooms"] += 1
            continue
        positives = set(placement_counts)
        for room_name, day, period in positives:
            room = room_map.get(room_name)
            if room:
                samples.append(_make_sample(1, "actual", task, course, class_group, room, day, period, teacher_map, stats))

        negative_candidates = [
            (room, day, period)
            for room in feasible_rooms[:80]
            for day, period in DAY_PERIODS
            if (str(room.get("name") or ""), day, period) not in positives
        ]
        rng.shuffle(negative_candidates)
        negative_limit = max(8, min(36, len(positives) * 4))
        for room, day, period in negative_candidates[:negative_limit]:
            samples.append(_make_sample(0, "alternative", task, course, class_group, room, day, period, teacher_map, stats))

    print(f"样本数: {len(samples)}")
    print(f"正样本: {sum(1 for row in samples if row['label'] == 1)}")
    print(f"负样本: {sum(1 for row in samples if row['label'] == 0)}")
    print(f"跳过统计: {dict(skip_counts)}")
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(samples)
    STATS_OUTPUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"输出: {OUTPUT}")
    print(f"统计: {STATS_OUTPUT}")
    return OUTPUT


def _make_sample(
    label: int,
    sample_type: str,
    task: dict[str, Any],
    course: dict[str, Any],
    class_group: dict[str, Any],
    room: dict[str, Any],
    day: int,
    period: int,
    teacher_map: dict[str, dict[str, Any]],
    stats: dict[str, Any],
) -> dict[str, Any]:
    course_code = str(task.get("course_code") or "")
    course_name = str(course.get("name") or "")
    teacher = str(task.get("teacher") or "")
    class_group_name = str(task.get("class_group") or "")
    class_major = str(class_group.get("major") or "")
    teacher_department = _teacher_department(teacher, teacher_map)
    room_name = str(room.get("name") or "")
    room_type = _norm(room.get("classroom_type"))
    required_room_type = _resolve_required_room_type(course, task)
    student_count = float(int(class_group.get("student_count") or 0))
    room_capacity = float(int(room.get("capacity") or 0))
    total_hours = float(task.get("total_hours") or course.get("hours") or 0)
    slot_key = f"{day}:{period}"
    room_slot_key = f"{room_name}|{slot_key}"
    return {
        "label": label,
        "course_code": course_code,
        "teacher": teacher,
        "class_group": class_group_name,
        "room_name": room_name,
        "day": day,
        "period": period,
        "sample_type": sample_type,
        "course_code_code": float(_stable_code(course_code)),
        "course_name_code": float(_stable_code(course_name)),
        "course_type_code": float(_stable_code(course.get("course_type"))),
        "teacher_name_code": float(_stable_code(teacher)),
        "teacher_department_code": float(_stable_code(teacher_department)),
        "class_group_name_code": float(_stable_code(class_group_name)),
        "class_group_major_code": float(_stable_code(class_major)),
        "class_grade": float(_extract_grade(class_group_name)),
        "class_no": float(_extract_class_no(class_group_name)),
        "student_count": student_count,
        "total_hours": total_hours,
        "total_lessons": total_hours / 2.0,
        "room_name_code": float(_stable_code(room_name)),
        "room_type_code": float(_stable_code(room_type)),
        "room_capacity": room_capacity,
        "capacity_margin": room_capacity - student_count,
        "capacity_ratio": student_count / max(1.0, room_capacity),
        "required_type_match": 1.0 if required_room_type and required_room_type == room_type else 0.0,
        "building_code": float(_building_code(room_name)),
        "day_of_week": float(day),
        "period_index": float(period),
        "is_early": 1.0 if period == 1 else 0.0,
        "is_late": 1.0 if period >= 4 else 0.0,
        "is_morning": 1.0 if period in (1, 2) else 0.0,
        "is_afternoon": 1.0 if period >= 3 else 0.0,
        "course_slot_frequency": _frequency(stats, "course_slot_frequency", course_code, slot_key),
        "teacher_slot_frequency": _frequency(stats, "teacher_slot_frequency", teacher, slot_key),
        "class_major_slot_frequency": _frequency(stats, "class_major_slot_frequency", class_major, slot_key),
        "room_slot_frequency": _frequency(stats, "room_slot_frequency", room_name, slot_key),
        "course_room_frequency": _frequency(stats, "course_room_frequency", course_code, room_name),
        "teacher_room_frequency": _frequency(stats, "teacher_room_frequency", teacher, room_name),
        "class_major_room_frequency": _frequency(stats, "class_major_room_frequency", class_major, room_name),
        "course_room_slot_frequency": _frequency(stats, "course_room_slot_frequency", course_code, room_slot_key),
        "teacher_room_slot_frequency": _frequency(stats, "teacher_room_slot_frequency", teacher, room_slot_key),
        "major_room_slot_frequency": _frequency(stats, "major_room_slot_frequency", class_major, room_slot_key),
        "global_room_slot_frequency": _frequency(stats, "global_room_slot_frequency", "", room_slot_key),
    }


def _build_frequency_stats(
    used: dict[tuple[str, str], Counter[tuple[str, int, int]]],
    task_map: dict[tuple[str, str], dict[str, Any]],
    class_groups: dict[str, dict[str, Any]],
    teacher_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    counters: dict[str, dict[str, Counter[str]] | Counter[str]] = {
        "course_slot_frequency": defaultdict(Counter),
        "teacher_slot_frequency": defaultdict(Counter),
        "class_major_slot_frequency": defaultdict(Counter),
        "room_slot_frequency": defaultdict(Counter),
        "course_room_frequency": defaultdict(Counter),
        "teacher_room_frequency": defaultdict(Counter),
        "class_major_room_frequency": defaultdict(Counter),
        "course_room_slot_frequency": defaultdict(Counter),
        "teacher_room_slot_frequency": defaultdict(Counter),
        "major_room_slot_frequency": defaultdict(Counter),
        "global_room_slot_frequency": Counter(),
    }
    for key, placements in used.items():
        task = task_map.get(key, {})
        course_code, class_group_name = key
        teacher = str(task.get("teacher") or "")
        class_major = str((class_groups.get(class_group_name) or {}).get("major") or "")
        for (room, day, period), count in placements.items():
            slot_key = f"{day}:{period}"
            room_slot_key = f"{room}|{slot_key}"
            counters["course_slot_frequency"][_norm(course_code)][slot_key] += count
            counters["teacher_slot_frequency"][_norm(teacher)][slot_key] += count
            counters["class_major_slot_frequency"][_norm(class_major)][slot_key] += count
            counters["room_slot_frequency"][_norm(room)][slot_key] += count
            counters["course_room_frequency"][_norm(course_code)][room] += count
            counters["teacher_room_frequency"][_norm(teacher)][room] += count
            counters["class_major_room_frequency"][_norm(class_major)][room] += count
            counters["course_room_slot_frequency"][_norm(course_code)][room_slot_key] += count
            counters["teacher_room_slot_frequency"][_norm(teacher)][room_slot_key] += count
            counters["major_room_slot_frequency"][_norm(class_major)][room_slot_key] += count
            counters["global_room_slot_frequency"][room_slot_key] += count
    return {
        name: _normalize_counter(counter) if isinstance(counter, Counter) else _normalize_nested_counter(counter)
        for name, counter in counters.items()
    }


def _is_feasible(task: dict[str, Any], course: dict[str, Any], class_group: dict[str, Any], room: dict[str, Any]) -> bool:
    capacity = int(room.get("capacity") or 0)
    student_count = int(class_group.get("student_count") or 0)
    if capacity < student_count:
        return False
    room_type = _norm(room.get("classroom_type"))
    required = _resolve_required_room_type(course, task)
    return bool(room_type) and room_type == required


def _resolve_required_room_type(course: dict[str, Any], task: dict[str, Any]) -> str:
    explicit = _norm(course.get("required_room_type"))
    if explicit:
        return explicit
    type_map = {
        "理论课": "普通教室",
        "上机课": "机房",
        "实践课": "普通教室",
        "体育课": "操场",
    }
    return type_map.get(_norm(task.get("course_type") or course.get("course_type")), "")


def _frequency(stats: dict[str, Any], section: str, key: str, item: str) -> float:
    data = stats.get(section) or {}
    if section == "global_room_slot_frequency":
        return float(data.get(item) or 0.0)
    return float((data.get(_norm(key)) or {}).get(item) or 0.0)


def _normalize_counter(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values()) or 1
    return {key: round(value / total, 6) for key, value in counter.items()}


def _normalize_nested_counter(counters: dict[str, Counter[str]]) -> dict[str, dict[str, float]]:
    return {key: _normalize_counter(counter) for key, counter in counters.items()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _teacher_department(teacher_name: str, teacher_map: dict[str, dict[str, Any]]) -> str:
    departments = (teacher_map.get(teacher_name) or {}).get("departments", [])
    return str(departments[0]).strip().lower() if departments else teacher_name.lower()


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


def _extract_grade(value: Any) -> int:
    text = str(value or "")
    for index in range(max(0, len(text) - 3)):
        part = text[index:index + 4]
        if part.isdigit() and 2000 <= int(part) <= 2100:
            return int(part)
    return 0


def _extract_class_no(value: Any) -> int:
    text = str(value or "")
    if "班" not in text:
        return 0
    before = text.split("班")[0]
    digits = ""
    for char in reversed(before):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return int(digits) if digits else 0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _period_start_to_index(value: Any) -> int:
    start = _safe_int(value)
    return (start + 1) // 2 if start > 0 else 0


if __name__ == "__main__":
    build()
