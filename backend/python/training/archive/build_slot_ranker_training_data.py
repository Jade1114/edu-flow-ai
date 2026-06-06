"""Build slot-ranker training samples from real timetables.

Positive samples = (course, class_group) → (day, period) actually used in history.
Negative samples = feasible (day, period) that the same task did NOT use.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from python.scheduling_v2.slot_ranker import SLOT_RANK_FEATURES

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT = DATA / "slot_ranker_samples.csv"
STATS_OUTPUT = DATA / "slot_ranker_stats.json"
METADATA_FIELDS = [
    "label",
    "course_code",
    "class_group",
    "day",
    "period",
    "sample_type",
]
FIELDS = METADATA_FIELDS + SLOT_RANK_FEATURES

# All possible (day, period) pairs
DAY_PERIODS = [(d, p) for d in range(1, 8) for p in range(1, 6)]


def build() -> Path:
    print("加载真实排课 JSONL...")
    timetables = _read_jsonl(DATA / "timetables.jsonl")
    tasks = _read_jsonl(DATA / "teaching_tasks.jsonl")
    courses = {str(row.get("code") or ""): row for row in _read_jsonl(DATA / "courses.jsonl")}
    teachers = _read_jsonl(DATA / "teachers.jsonl")
    teacher_map = {
        str(entry.get("name") or ""): {"departments": entry.get("departments", [])}
        for entry in teachers
    }
    class_groups = {str(row.get("name") or ""): row for row in _read_jsonl(DATA / "class_groups.jsonl")}

    task_map = {
        (str(row.get("course_code") or ""), str(row.get("class_group") or "")): row
        for row in tasks
    }

    # Collect historical (day, period) usage per (course_code, class_group)
    used_slots: dict[tuple[str, str], Counter[tuple[int, int]]] = defaultdict(Counter)
    skip_counts: Counter[str] = Counter()
    for entry in timetables:
        key = (str(entry.get("course_code") or ""), str(entry.get("class_group") or ""))
        if key not in task_map:
            skip_counts["missing_task"] += 1
            continue
        day = _safe_int(entry.get("day"))
        period = _period_start_to_index(entry.get("period_start"))
        if day < 1 or day > 7 or period < 1 or period > 5:
            skip_counts["invalid_day_period"] += 1
            continue
        used_slots[key][(day, period)] += 1

    stats = _build_frequency_stats(used_slots, task_map, courses, class_groups, teacher_map)

    rng = random.Random(42)
    samples: list[dict[str, Any]] = []

    for key, slot_counts in used_slots.items():
        task = task_map.get(key)
        if not task:
            continue
        course = courses.get(key[0], {})
        class_group = class_groups.get(key[1], {})
        if not course:
            skip_counts["missing_course"] += 1
            continue
        if not class_group:
            skip_counts["missing_class_group"] += 1
            continue

        positive_slots = set(slot_counts)
        feasible_slots = _feasible_slots(task, course, class_group)

        if not feasible_slots:
            continue

        for day, period in positive_slots:
            if (day, period) in feasible_slots:
                samples.append(_make_sample(1, "actual", task, course, class_group, day, period, teacher_map, stats))

        negatives = [sp for sp in feasible_slots if sp not in positive_slots]
        rng.shuffle(negatives)
        for day, period in negatives[: max(6, min(20, len(positive_slots) * 4))]:
            samples.append(_make_sample(0, "alternative", task, course, class_group, day, period, teacher_map, stats))

    print(f"样本数: {len(samples)}")
    print(f"正样本: {sum(1 for row in samples if row['label'] == 1)}")
    print(f"负样本: {sum(1 for row in samples if row['label'] == 0)}")
    print(f"跳过统计: {dict(skip_counts)}")

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(samples)
    STATS_OUTPUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"输出: {OUTPUT}")
    print(f"统计: {STATS_OUTPUT}")
    return OUTPUT


def _feasible_slots(
    task: dict[str, Any],
    course: dict[str, Any],
    class_group: dict[str, Any],
) -> list[tuple[int, int]]:
    """All (day, period) pairs that are feasible for this task."""
    # For now, all day_periods are feasible.
    # Future: add teacher hard-unavailable constraints here.
    return list(DAY_PERIODS)


def _make_sample(
    label: int,
    sample_type: str,
    task: dict[str, Any],
    course: dict[str, Any],
    class_group: dict[str, Any],
    day: int,
    period: int,
    teacher_map: dict[str, dict[str, Any]] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    teacher_name = str(task.get("teacher") or "")
    teacher_info = (teacher_map or {}).get(teacher_name, {})
    departments = teacher_info.get("departments", [])
    teacher_dept = str(departments[0]).strip().lower() if departments else teacher_name.lower()

    class_major = str(class_group.get("major") or "").strip().lower()
    cg_name = str(task.get("class_group") or "").strip().lower()
    course_code = str(task.get("course_code") or "")
    total_hours = float(task.get("total_hours") or course.get("hours") or 0)
    history = _slot_history_features(course_code, teacher_dept, class_major, day, period, stats or {})

    row = {
        "label": label,
        "course_code": course_code,
        "class_group": cg_name,
        "day": day,
        "period": period,
        "sample_type": sample_type,
        "course_code_code": float(_stable_code(course_code)),
        "class_group_name_code": float(_stable_code(cg_name)),
        "teacher_department_code": float(_stable_code(teacher_dept)),
        "class_group_major_code": float(_stable_code(class_major)),
        "course_type_code": float(_stable_code(course.get("course_type"))),
        "total_hours": total_hours,
        "total_lessons": total_hours / 2.0,
        "student_count": float(int(class_group.get("student_count") or 0)),
        "day_of_week": float(day),
        "period_index": float(period),
        "is_early": 1.0 if period == 1 else 0.0,
        "is_late": 1.0 if period >= 4 else 0.0,
        "is_morning": 1.0 if period in (1, 2) else 0.0,
        "is_afternoon": 1.0 if period >= 3 else 0.0,
        **history,
    }
    return row


def _build_frequency_stats(
    used_slots: dict[tuple[str, str], Counter[tuple[int, int]]],
    task_map: dict[tuple[str, str], dict[str, Any]],
    courses: dict[str, dict[str, Any]],
    class_groups: dict[str, dict[str, Any]],
    teacher_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global_counts: Counter[str] = Counter()
    course_counts: dict[str, Counter[str]] = defaultdict(Counter)
    teacher_counts: dict[str, Counter[str]] = defaultdict(Counter)
    major_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for key, slot_counts in used_slots.items():
        task = task_map.get(key)
        if not task:
            continue
        course_code, class_group_name = key
        class_group = class_groups.get(class_group_name, {})
        teacher_name = str(task.get("teacher") or "")
        teacher_dept = _teacher_department(teacher_name, teacher_map)
        class_major = _norm(class_group.get("major"))
        for (day, period), count in slot_counts.items():
            slot_key = f"{day}:{period}"
            global_counts[slot_key] += count
            course_counts[_norm(course_code)][slot_key] += count
            teacher_counts[_norm(teacher_dept)][slot_key] += count
            major_counts[_norm(class_major)][slot_key] += count

    return {
        "global_slot_frequency": _normalize_counter(global_counts),
        "course_slot_frequency": _normalize_nested_counter(course_counts),
        "teacher_slot_frequency": _normalize_nested_counter(teacher_counts),
        "class_major_slot_frequency": _normalize_nested_counter(major_counts),
    }


def _slot_history_features(
    course_code: str,
    teacher_dept: str,
    class_major: str,
    day: int,
    period: int,
    stats: dict[str, Any],
) -> dict[str, float]:
    slot = f"{day}:{period}"
    return {
        "course_slot_frequency": _frequency(stats, "course_slot_frequency", course_code, slot),
        "teacher_slot_frequency": _frequency(stats, "teacher_slot_frequency", teacher_dept, slot),
        "class_major_slot_frequency": _frequency(stats, "class_major_slot_frequency", class_major, slot),
        "global_slot_frequency": _frequency(stats, "global_slot_frequency", "", slot),
    }


def _frequency(stats: dict[str, Any], section: str, key: str, slot: str) -> float:
    data = stats.get(section) or {}
    if section == "global_slot_frequency":
        return float(data.get(slot) or 0.0)
    return float((data.get(_norm(key)) or {}).get(slot) or 0.0)


def _normalize_counter(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values()) or 1
    return {key: round(value / total, 6) for key, value in counter.items()}


def _normalize_nested_counter(counters: dict[str, Counter[str]]) -> dict[str, dict[str, float]]:
    return {key: _normalize_counter(counter) for key, counter in counters.items()}


def _teacher_department(teacher_name: str, teacher_map: dict[str, dict[str, Any]]) -> str:
    teacher_info = teacher_map.get(teacher_name, {})
    departments = teacher_info.get("departments", [])
    return str(departments[0]).strip().lower() if departments else teacher_name.lower()


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


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _period_start_to_index(value: Any) -> int:
    period_start = _safe_int(value)
    if period_start <= 0:
        return 0
    return (period_start + 1) // 2


if __name__ == "__main__":
    build()
