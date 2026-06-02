"""Analyze real timetable resource/course distributions from JSONL data."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
DEFAULT_TOP_N = 30
ALLOWED_COURSE_TYPES = frozenset({"理论课", "上机课"})
ALLOWED_CLASSROOM_TYPES = frozenset({"普通教室", "机房"})


def analyze_real_timetable_distribution(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    data_root = Path(data_dir)
    timetables = _read_jsonl(data_root / "timetables.jsonl")
    courses = _by_key(_read_jsonl(data_root / "courses.jsonl"), "code")
    classrooms = _by_key(_read_jsonl(data_root / "classrooms.jsonl"), "name")
    top_n = max(1, int(top_n))

    all_rows = [_enrich(row, courses, classrooms) for row in timetables]
    formal_rows = [
        row for row in all_rows
        if row["course_type"] in ALLOWED_COURSE_TYPES and _is_supported_classroom(row)
    ]

    return {
        "data_dir": str(data_root),
        "all": _section(all_rows, top_n),
        "formal": _section(formal_rows, top_n),
        "filters": {
            "formal_course_types": sorted(ALLOWED_COURSE_TYPES),
            "formal_classroom_types": sorted(ALLOWED_CLASSROOM_TYPES),
            "excluded_count": len(all_rows) - len(formal_rows),
        },
    }


def _section(rows: list[dict[str, Any]], top_n: int) -> dict[str, Any]:
    course_type_counts = Counter(row["course_type"] or "<未知>" for row in rows)
    classroom_type_counts = Counter(row["classroom_type"] or "<未知>" for row in rows)
    room_counts = Counter(row["room"] or "<空教室>" for row in rows)
    slot_counts = Counter((row["day"], row["period_index"]) for row in rows)
    room_slot_counts = Counter((row["room"] or "<空教室>", row["day"], row["period_index"]) for row in rows)
    room_week_slot_counts = Counter((row["room"] or "<空教室>", row["week"], row["day"], row["period_index"]) for row in rows)
    course_counts = Counter((row["course_code"], row["course_name"], row["course_type"]) for row in rows)
    room_course_type_counts = Counter((row["room"] or "<空教室>", row["course_type"] or "<未知>") for row in rows)
    room_distinct_slots: dict[str, set[tuple[int, int]]] = defaultdict(set)
    room_distinct_week_slots: dict[str, set[tuple[int, int, int]]] = defaultdict(set)
    room_distinct_courses: dict[str, set[str]] = defaultdict(set)
    room_distinct_classes: dict[str, set[str]] = defaultdict(set)
    course_type_room_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        room = row["room"] or "<空教室>"
        course_type = row["course_type"] or "<未知>"
        room_distinct_slots[room].add((row["day"], row["period_index"]))
        room_distinct_week_slots[room].add((row["week"], row["day"], row["period_index"]))
        room_distinct_courses[room].add(row["course_code"])
        room_distinct_classes[room].add(row["class_group"])
        course_type_room_counts[course_type][room] += 1

    return {
        "row_count": len(rows),
        "distinct_room_count": len(room_counts),
        "distinct_course_count": len(course_counts),
        "distinct_class_group_count": len({row["class_group"] for row in rows}),
        "course_type_counts": _top_scalar(course_type_counts, top_n),
        "classroom_type_counts": _top_scalar(classroom_type_counts, top_n),
        "top_courses": _top_course(course_counts, top_n),
        "top_rooms": _top_rooms(
            room_counts,
            room_distinct_slots,
            room_distinct_week_slots,
            room_distinct_courses,
            room_distinct_classes,
            top_n,
        ),
        "top_slots": _top_slots(slot_counts, top_n),
        "top_room_slots": _top_room_slots(room_slot_counts, top_n),
        "top_room_week_slots": _top_room_week_slots(room_week_slot_counts, top_n),
        "top_room_course_types": _top_room_course_types(room_course_type_counts, top_n),
        "course_type_top_rooms": {
            course_type: _top_scalar(counter, top_n)
            for course_type, counter in sorted(course_type_room_counts.items())
        },
    }


def _enrich(
    row: dict[str, Any],
    courses: dict[str, dict[str, Any]],
    classrooms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    course_code = str(row.get("course_code") or "").strip()
    room = str(row.get("room") or "").strip()
    course = courses.get(course_code) or {}
    classroom = classrooms.get(room) or {}
    return {
        "class_group": str(row.get("class_group") or "").strip(),
        "grade": _safe_int(row.get("grade")),
        "major": str(row.get("major") or "").strip(),
        "class_no": _safe_int(row.get("class_no")),
        "week": _safe_int(row.get("week")),
        "day": _safe_int(row.get("day")),
        "period_label": str(row.get("period_label") or "").strip(),
        "period_start": _safe_int(row.get("period_start")),
        "period_index": _period_start_to_index(row.get("period_start")),
        "course_code": course_code,
        "course_name": str(course.get("name") or "").strip(),
        "course_type": str(course.get("course_type") or "").strip(),
        "required_room_type": str(course.get("required_room_type") or "").strip(),
        "room": room,
        "classroom_type": str(classroom.get("classroom_type") or "").strip(),
        "classroom_capacity": _safe_int(classroom.get("capacity")),
    }


def _is_supported_classroom(row: dict[str, Any]) -> bool:
    room_type = str(row.get("classroom_type") or "").strip()
    name = str(row.get("room") or "").strip().lower()
    if room_type not in ALLOWED_CLASSROOM_TYPES:
        return False
    if name.startswith("xn") or name.startswith("虚拟"):
        return False
    return "操场" not in name and "体育" not in name


def _top_scalar(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [{"value": key, "count": count} for key, count in counter.most_common(top_n)]


def _top_course(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [
        {"course_code": code, "course_name": name, "course_type": course_type, "count": count}
        for (code, name, course_type), count in counter.most_common(top_n)
    ]


def _top_rooms(
    room_counts: Counter,
    room_distinct_slots: dict[str, set[tuple[int, int]]],
    room_distinct_week_slots: dict[str, set[tuple[int, int, int]]],
    room_distinct_courses: dict[str, set[str]],
    room_distinct_classes: dict[str, set[str]],
    top_n: int,
) -> list[dict[str, Any]]:
    return [
        {
            "room": room,
            "count": count,
            "distinct_day_periods": len(room_distinct_slots[room]),
            "distinct_week_day_periods": len(room_distinct_week_slots[room]),
            "distinct_courses": len(room_distinct_courses[room]),
            "distinct_class_groups": len(room_distinct_classes[room]),
        }
        for room, count in room_counts.most_common(top_n)
    ]


def _top_slots(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [
        {"day_of_week": day, "period_index": period, "count": count}
        for (day, period), count in counter.most_common(top_n)
    ]


def _top_room_slots(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [
        {"room": room, "day_of_week": day, "period_index": period, "count": count}
        for (room, day, period), count in counter.most_common(top_n)
    ]


def _top_room_week_slots(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [
        {"room": room, "week": week, "day_of_week": day, "period_index": period, "count": count}
        for (room, week, day, period), count in counter.most_common(top_n)
    ]


def _top_room_course_types(counter: Counter, top_n: int) -> list[dict[str, Any]]:
    return [
        {"room": room, "course_type": course_type, "count": count}
        for (room, course_type), count in counter.most_common(top_n)
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or "").strip(): row for row in rows if str(row.get(key) or "").strip()}


def _period_start_to_index(value: Any) -> int:
    period_start = _safe_int(value)
    if period_start <= 0:
        return 0
    return (period_start + 1) // 2


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _print_report(report: dict[str, Any]) -> None:
    print("Real timetable distribution")
    print(f"- data_dir: {report['data_dir']}")
    print(f"- excluded by formal filter: {report['filters']['excluded_count']}")
    for section_name in ("all", "formal"):
        section = report[section_name]
        print(f"\n[{section_name}]")
        print(f"- rows: {section['row_count']}")
        print(f"- rooms: {section['distinct_room_count']}")
        print(f"- courses: {section['distinct_course_count']}")
        print(f"- class_groups: {section['distinct_class_group_count']}")
        print("- course types:")
        for item in section["course_type_counts"][:10]:
            print(f"  {item['value']}: {item['count']}")
        print("- classroom types:")
        for item in section["classroom_type_counts"][:10]:
            print(f"  {item['value']}: {item['count']}")
        print("- top rooms:")
        for item in section["top_rooms"][:10]:
            print(
                "  "
                f"{item['room']}: count={item['count']} "
                f"day_periods={item['distinct_day_periods']} "
                f"week_slots={item['distinct_week_day_periods']} "
                f"courses={item['distinct_courses']} classes={item['distinct_class_groups']}"
            )
        print("- top slots:")
        for item in section["top_slots"][:10]:
            print(f"  day={item['day_of_week']} period={item['period_index']}: {item['count']}")
        print("- top room+slot:")
        for item in section["top_room_slots"][:10]:
            print(
                "  "
                f"{item['room']} day={item['day_of_week']} "
                f"period={item['period_index']}: {item['count']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze real timetable room/course distributions.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--output", default=None)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args()

    report = analyze_real_timetable_distribution(args.data_dir, top_n=args.top_n)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)


if __name__ == "__main__":
    main()
