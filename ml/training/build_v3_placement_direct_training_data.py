"""Build V3 direct-placement multiclass training data.

Target contract:
  input  = teaching-task features
  output = resource_key = classroom_name | day_of_week | period_index

Rows are de-duplicated by source_key + resource_key so a full-semester weekly
repeat does not overweight one resource.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT_PATH = DATA_DIR / "v3_placement_direct_training_samples.csv"
ALLOWED_COURSE_TYPES = frozenset({"理论课", "上机课"})
ALLOWED_CLASSROOM_TYPES = frozenset({"普通教室", "机房"})

FIELDS = [
    "source_key",
    "resource_key",
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
    "classroom_name",
    "classroom_type",
    "classroom_capacity",
    "day_of_week",
    "period_index",
    "observed_weeks",
    "source_period_labels",
]


def build(*, data_dir: Path = DATA_DIR, output_path: Path = OUTPUT_PATH) -> Path:
    courses = _by_key(_read_jsonl(data_dir / "courses.jsonl"), "code")
    teachers = _by_key(_read_jsonl(data_dir / "teachers.jsonl"), "name")
    class_groups = _by_key(_read_jsonl(data_dir / "class_groups.jsonl"), "name")
    classrooms = _by_key(_read_jsonl(data_dir / "classrooms.jsonl"), "name")
    teaching_tasks = _index_teaching_tasks(_read_jsonl(data_dir / "teaching_tasks.jsonl"))
    timetables = _read_jsonl(data_dir / "timetables.jsonl")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    skip_counts: Counter[str] = Counter()
    for timetable in timetables:
        source = _resolve_source(timetable, teaching_tasks, courses, teachers, class_groups, classrooms)
        if source is None:
            skip_counts["unresolved"] += 1
            continue
        if not _is_supported_course(source["course"]):
            skip_counts["unsupported_course_type"] += 1
            continue
        if not _is_supported_classroom(source["classroom"]):
            skip_counts["unsupported_classroom"] += 1
            continue
        row = _make_row(source, timetable)
        key = (row["source_key"], row["resource_key"])
        if key not in grouped:
            grouped[key] = row
            grouped[key]["_weeks"] = set()
            grouped[key]["_period_labels"] = set()
        grouped[key]["_weeks"].add(_safe_int(timetable.get("week")))
        label = str(timetable.get("period_label") or "").strip()
        if label:
            grouped[key]["_period_labels"].add(label)

    rows = []
    for row in grouped.values():
        row = dict(row)
        weeks = sorted(week for week in row.pop("_weeks") if week > 0)
        labels = sorted(row.pop("_period_labels"))
        row["observed_weeks"] = ",".join(str(week) for week in weeks)
        row["source_period_labels"] = ",".join(labels)
        rows.append(row)
    rows.sort(key=lambda item: (item["source_key"], item["resource_key"]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"输出: {output_path}")
    print(f"样本数: {len(rows)}")
    print(f"source_key: {len({row['source_key'] for row in rows})}")
    print(f"resource_key: {len({row['resource_key'] for row in rows})}")
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
    if not room_name:
        return None
    task = teaching_tasks.get((course_code, class_name))
    course = courses.get(course_code)
    class_group = class_groups.get(class_name)
    classroom = classrooms.get(room_name)
    if not task or not course or not class_group or not classroom:
        return None
    teacher_name = str(task.get("teacher") or "").strip()
    teacher = teachers.get(teacher_name) or {}
    day = _safe_int(timetable.get("day"))
    period = _period_start_to_index(timetable.get("period_start"))
    if day < 1 or day > 5 or period < 1 or period > 5:
        return None
    teacher_no, teacher_no_source = _teacher_no(teacher_name, teacher)
    return {
        "task": task,
        "course": course,
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


def _make_row(source: dict[str, Any], timetable: dict[str, Any]) -> dict[str, Any]:
    course = source["course"]
    task = source["task"]
    class_group = source["class_group"]
    classroom = source["classroom"]
    classroom_name = str(classroom.get("name") or timetable.get("room") or "").strip()
    day = int(source["day_of_week"])
    period = int(source["period_index"])
    return {
        "source_key": source["source_key"],
        "resource_key": f"{classroom_name}|{day}|{period}",
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
        "student_count": _safe_int(class_group.get("student_count")),
        "total_hours": float(task.get("total_hours") or course.get("hours") or 0),
        "course_type": str(course.get("course_type") or ""),
        "required_room_type": _required_room_type(course, task),
        "classroom_name": classroom_name,
        "classroom_type": str(classroom.get("classroom_type") or ""),
        "classroom_capacity": _safe_int(classroom.get("capacity")),
        "day_of_week": day,
        "period_index": period,
        "observed_weeks": "",
        "source_period_labels": "",
    }


def _index_teaching_tasks(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        key = (str(row.get("course_code") or "").strip(), str(row.get("class_group") or "").strip())
        result.setdefault(key, row)
    return result


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


def _required_room_type(course: dict[str, Any], task: dict[str, Any]) -> str:
    explicit = str(course.get("required_room_type") or task.get("required_room_type") or "").strip()
    if explicit:
        return explicit
    return {"理论课": "普通教室", "上机课": "机房"}.get(str(course.get("course_type") or "").strip(), "")


def _teacher_no(teacher_name: str, teacher: dict[str, Any]) -> tuple[str, str]:
    for key in ("teacher_no", "employee_no", "employeeNo"):
        value = str(teacher.get(key) or "").strip()
        if value:
            return value, key
    return f"TEACHER_{teacher_name}", "generated"


def _period_start_to_index(value: Any) -> int:
    period_start = _safe_int(value)
    return (period_start + 1) // 2 if period_start > 0 else 0


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


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or "").strip(): row for row in rows if str(row.get(key) or "").strip()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V3 direct placement multiclass training data.")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    build(data_dir=Path(args.data_dir), output_path=Path(args.output))


if __name__ == "__main__":
    main()
