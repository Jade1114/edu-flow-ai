"""Parse one class schedule .xlsx into CSV files.

This parser targets class timetable Excel files, not generic course-list files.
It is read-only and writes normalized CSV artifacts for later review/LLM steps.

Outputs:
- courses.csv
- teachers.csv
- classrooms.csv
- class_groups.csv
- teaching_tasks.csv
- timetable_occurrences.csv
- parse_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from placement_model import OUTPUT_DIR as PLACEMENT_OUTPUT_DIR

DEFAULT_OUTPUT_ROOT = PLACEMENT_OUTPUT_DIR / "schedule_imports"
PUBLIC_PHYSICAL_EDUCATION = "公共体育"
UNSCHEDULABLE_COURSES = {PUBLIC_PHYSICAL_EDUCATION}
WEEKDAY_LABELS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "日": 7,
    "天": 7,
}
DETAIL_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fa5A-Za-z0-9·（）()《》\-—_\s]+?)"
    r"\((?P<code>[^()\[\]]+)\)"
    r"(?:\(ID\[[^\]]*\]学分\[(?P<credits>[^\]]*)\]\)|.*?学分\[(?P<credits_alt>[^\]]*)\])?"
    r"\s*时\[(?P<hours>[^\]]*)\]"
    r"\s*师\[(?P<teachers>[^\]]*)\]"
    r"\s*室\[(?P<rooms>[^\]]*)\]",
    re.S,
)
COURSE_CODE_PATTERN = re.compile(r"^[\u4e00-\u9fa5]{1,4}\d{2,4}$")
CLASSROOM_PATTERN = re.compile(r"^\d{4,6}$")
META_PATTERN = re.compile(
    r"(?P<academic_year>\d{4}-\d{4})学年第(?P<semester>\d+)学期"
    r"(?P<department>.+?)\(学院\)"
    r"(?P<major>.+?)\(专业\)"
    r"(?P<class_name>.+?)\(班级\)课表共(?P<student_count>\d+)人"
)
CELL_REF_PATTERN = re.compile(r"([A-Z]+)(\d+)")


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    value: str


@dataclass(frozen=True)
class CourseDetail:
    course_code: str
    course_name: str
    credits: str
    required_hours: str
    teachers: list[str]
    rooms: list[str]
    raw_text: str


@dataclass(frozen=True)
class Occurrence:
    class_name: str
    course_code: str
    classroom_name: str
    day_of_week: int
    period_index: int
    row_index: int
    col_index: int
    sheet_name: str
    raw_cell: str


def parse_schedule_excel(
    *,
    input_path: Path,
    output_dir: Path | None = None,
    class_name: str | None = None,
    major: str | None = None,
    department: str | None = None,
    grade: str | None = None,
    student_count: int | None = None,
    task_batch: str = "DEFAULT",
) -> dict[str, Any]:
    if input_path.suffix.lower() != ".xlsx":
        raise SystemExit("当前解析器第一版只支持 .xlsx 文件")

    output_dir = output_dir or DEFAULT_OUTPUT_ROOT / input_path.stem
    workbook = _read_xlsx(input_path)
    if not workbook:
        raise SystemExit("Excel 中没有可解析的 sheet")

    first_sheet_name = next(iter(workbook.keys()))
    first_sheet = workbook[first_sheet_name]
    meta = _parse_meta(first_sheet, fallback={
        "class_name": class_name,
        "major": major,
        "department": department,
        "grade": grade,
        "student_count": student_count,
    })
    class_name_value = str(meta.get("class_name") or class_name or input_path.stem).strip()

    details_by_code: dict[str, CourseDetail] = {}
    occurrences: list[Occurrence] = []
    warnings: list[dict[str, Any]] = []

    for sheet_name, cells in workbook.items():
        sheet_details = _extract_course_details(cells)
        for detail in sheet_details:
            details_by_code.setdefault(detail.course_code, detail)
        day_cols = _detect_day_columns(cells)
        period_rows = _detect_period_rows(cells)
        if not day_cols:
            warnings.append({"sheet": sheet_name, "warning": "未识别到星期列，使用 B-F 作为周一至周五兜底"})
            day_cols = {col: col - 1 for col in range(2, 7)}
        if not period_rows:
            warnings.append({"sheet": sheet_name, "warning": "未识别到节次行，尝试按行号顺序兜底"})
            period_rows = _fallback_period_rows(cells)
        occurrences.extend(_extract_occurrences(cells, sheet_name, class_name_value, day_cols, period_rows))

    code_order = _ordered_codes(occurrences, details_by_code)
    courses = _build_courses(code_order, details_by_code, occurrences)
    teachers = _build_teachers(details_by_code)
    classrooms = _build_classrooms(details_by_code, occurrences, courses)
    class_groups = [_build_class_group(meta, class_name_value)]
    teaching_tasks = _build_teaching_tasks(class_name_value, task_batch, courses, details_by_code, occurrences)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "courses.csv", courses, [
        "course_code", "course_name", "credits", "required_hours", "course_type", "required_room_type",
        "schedulable", "exclude_reason", "raw_text",
    ])
    _write_csv(output_dir / "teachers.csv", teachers, ["teacher_name", "department", "title", "raw_source"])
    _write_csv(output_dir / "classrooms.csv", classrooms, ["classroom_name", "classroom_type", "capacity", "status", "raw_source"])
    _write_csv(output_dir / "class_groups.csv", class_groups, [
        "class_name", "major", "department", "grade", "student_count", "academic_year", "semester",
    ])
    _write_csv(output_dir / "teaching_tasks.csv", teaching_tasks, [
        "course_code", "course_name", "teacher_name", "class_name", "total_hours", "required_room_type",
        "task_batch", "schedulable", "exclude_reason", "source",
    ])
    _write_csv(output_dir / "timetable_occurrences.csv", [_occurrence_row(item, details_by_code) for item in occurrences], [
        "class_name", "course_code", "course_name", "teacher_name", "classroom_name", "day_of_week",
        "period_index", "row_index", "col_index", "sheet_name", "raw_cell",
    ])

    report = {
        "status": "ok",
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "sheet_count": len(workbook),
        "sheets": list(workbook.keys()),
        "class_meta": class_groups[0],
        "counts": {
            "courses": len(courses),
            "teachers": len(teachers),
            "classrooms": len(classrooms),
            "class_groups": len(class_groups),
            "teaching_tasks": len(teaching_tasks),
            "timetable_occurrences": len(occurrences),
        },
        "warnings": warnings,
        "unmatched_occurrence_codes": sorted({
            item.course_code
            for item in occurrences
            if item.course_code not in details_by_code and item.course_code not in UNSCHEDULABLE_COURSES
        }),
    }
    (output_dir / "parse_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _read_xlsx(path: Path) -> dict[str, list[Cell]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_names = _read_sheet_names(archive)
        result: dict[str, list[Cell]] = {}
        for index, sheet_name in enumerate(sheet_names, start=1):
            sheet_path = f"xl/worksheets/sheet{index}.xml"
            if sheet_path not in archive.namelist():
                continue
            result[sheet_name] = _read_sheet_cells(archive, sheet_path, shared_strings)
        return result


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall(".//{*}si"):
        parts = [node.text or "" for node in si.findall(".//{*}t")]
        strings.append("".join(parts))
    return strings


def _read_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    names = [sheet.attrib.get("name") or f"Sheet{idx}" for idx, sheet in enumerate(root.findall(".//{*}sheet"), start=1)]
    return names or ["Sheet1"]


def _read_sheet_cells(archive: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]) -> list[Cell]:
    root = ET.fromstring(archive.read(sheet_path))
    cells: list[Cell] = []
    for cell in root.findall(".//{*}c"):
        ref = cell.attrib.get("r", "")
        match = CELL_REF_PATTERN.match(ref)
        if not match:
            continue
        col = _col_to_index(match.group(1))
        row = int(match.group(2))
        value = _cell_value(cell, shared_strings)
        if value.strip():
            cells.append(Cell(row=row, col=col, value=value.strip()))
    return cells


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//{*}t"))
    value_node = cell.find("{*}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text
    if cell_type == "s":
        index = _safe_int(raw_value)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return raw_value


def _parse_meta(cells: list[Cell], fallback: dict[str, Any]) -> dict[str, Any]:
    text_candidates = [cell.value for cell in sorted(cells, key=lambda item: (item.row, item.col))[:20]]
    joined = " ".join(text_candidates)
    match = META_PATTERN.search(joined)
    meta = {
        "academic_year": "",
        "semester": "",
        "department": fallback.get("department") or "",
        "major": fallback.get("major") or "",
        "class_name": fallback.get("class_name") or "",
        "grade": fallback.get("grade") or "",
        "student_count": fallback.get("student_count") or 0,
    }
    if match:
        meta.update(match.groupdict())
        meta["grade"] = _infer_grade(meta["class_name"])
        meta["student_count"] = _safe_int(meta["student_count"])
    if not meta.get("grade") and meta.get("class_name"):
        meta["grade"] = _infer_grade(str(meta["class_name"]))
    return meta


def _extract_course_details(cells: list[Cell]) -> list[CourseDetail]:
    details: list[CourseDetail] = []
    for cell in cells:
        if "学分[" not in cell.value or "师[" not in cell.value or "时[" not in cell.value:
            continue
        for match in DETAIL_PATTERN.finditer(cell.value):
            raw_text = match.group(0).strip()
            code = _clean_token(match.group("code"))
            details.append(CourseDetail(
                course_code=code,
                course_name=_clean_course_name(match.group("name")),
                credits=_clean_token(match.group("credits") or match.group("credits_alt") or ""),
                required_hours=_clean_token(match.group("hours")),
                teachers=_split_list(match.group("teachers")),
                rooms=_split_list(match.group("rooms")),
                raw_text=raw_text,
            ))
    return details


def _detect_day_columns(cells: list[Cell]) -> dict[int, int]:
    result: dict[int, int] = {}
    for cell in cells:
        value = cell.value.replace("星期", "周")
        for label, day in WEEKDAY_LABELS.items():
            if f"周{label}" in value or f"星期{label}" in cell.value:
                result[cell.col] = day
    return result


def _detect_period_rows(cells: list[Cell]) -> dict[int, int]:
    result: dict[int, int] = {}
    for cell in cells:
        if cell.col > 3:
            continue
        value = cell.value.strip()
        match = re.search(r"第?([1-9]\d*)节", value)
        if not match:
            match = re.fullmatch(r"([1-9]\d*)", value)
        if match:
            period = _safe_int(match.group(1))
            if 1 <= period <= 12:
                result[cell.row] = period
    return result


def _fallback_period_rows(cells: list[Cell]) -> dict[int, int]:
    rows = sorted({cell.row for cell in cells if cell.row > 1})
    return {row: index for index, row in enumerate(rows[:12], start=1)}


def _extract_occurrences(
    cells: list[Cell],
    sheet_name: str,
    class_name: str,
    day_cols: dict[int, int],
    period_rows: dict[int, int],
) -> list[Occurrence]:
    result: list[Occurrence] = []
    for cell in cells:
        day = day_cols.get(cell.col)
        period = period_rows.get(cell.row)
        if not day or not period:
            continue
        parsed = _parse_timetable_cell(cell.value)
        for course_code, classroom_name in parsed:
            result.append(Occurrence(
                class_name=class_name,
                course_code=course_code,
                classroom_name=classroom_name,
                day_of_week=day,
                period_index=period,
                row_index=cell.row,
                col_index=cell.col,
                sheet_name=sheet_name,
                raw_cell=cell.value,
            ))
    return result


def _parse_timetable_cell(value: str) -> list[tuple[str, str]]:
    text = value.replace("\r", "\n").replace("，", " ").replace(",", " ").replace("；", " ").replace(";", " ")
    chunks = [chunk.strip() for chunk in re.split(r"[\n/]+", text) if chunk.strip()]
    result: list[tuple[str, str]] = []
    for chunk in chunks:
        if PUBLIC_PHYSICAL_EDUCATION in chunk:
            result.append((PUBLIC_PHYSICAL_EDUCATION, ""))
            continue
        tokens = [_clean_token(token) for token in re.split(r"\s+", chunk) if _clean_token(token)]
        course_codes = [token for token in tokens if COURSE_CODE_PATTERN.match(token)]
        classrooms = [token for token in tokens if CLASSROOM_PATTERN.match(token)]
        if not course_codes:
            continue
        classroom = classrooms[0] if classrooms else ""
        for code in course_codes:
            result.append((code, classroom))
    return result


def _build_courses(code_order: list[str], details_by_code: dict[str, CourseDetail], occurrences: list[Occurrence]) -> list[dict[str, Any]]:
    rows = []
    occurrence_rooms: dict[str, set[str]] = {}
    for item in occurrences:
        if item.classroom_name:
            occurrence_rooms.setdefault(item.course_code, set()).add(item.classroom_name)
    for code in code_order:
        detail = details_by_code.get(code)
        course_name = detail.course_name if detail else code
        course_type = _infer_course_type(course_name, detail.rooms if detail else list(occurrence_rooms.get(code, [])))
        schedulable, exclude_reason = _schedulable_state(code, course_name)
        rows.append({
            "course_code": code,
            "course_name": course_name,
            "credits": detail.credits if detail else "",
            "required_hours": detail.required_hours if detail else "",
            "course_type": course_type,
            "required_room_type": _required_room_type(course_type, schedulable),
            "schedulable": str(schedulable).lower(),
            "exclude_reason": exclude_reason,
            "raw_text": detail.raw_text if detail else "",
        })
    return rows


def _build_teachers(details_by_code: dict[str, CourseDetail]) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    for detail in details_by_code.values():
        for teacher in detail.teachers:
            seen.setdefault(teacher, detail.raw_text)
    return [{"teacher_name": name, "department": "", "title": "", "raw_source": raw} for name, raw in sorted(seen.items())]


def _build_classrooms(details_by_code: dict[str, CourseDetail], occurrences: list[Occurrence], courses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    course_type_by_code = {str(row["course_code"]): str(row["course_type"]) for row in courses}
    rooms: dict[str, set[str]] = {}
    for detail in details_by_code.values():
        for room in detail.rooms:
            rooms.setdefault(room, set()).add("course_detail")
    for item in occurrences:
        if item.classroom_name:
            rooms.setdefault(item.classroom_name, set()).add("timetable")
    result = []
    for room, sources in sorted(rooms.items()):
        linked_codes = {item.course_code for item in occurrences if item.classroom_name == room}
        room_type = "机房" if any(course_type_by_code.get(code) == "上机课" for code in linked_codes) else "普通教室"
        result.append({
            "classroom_name": room,
            "classroom_type": room_type,
            "capacity": 80,
            "status": "ACTIVE",
            "raw_source": "+".join(sorted(sources)),
        })
    return result


def _build_class_group(meta: dict[str, Any], class_name: str) -> dict[str, Any]:
    return {
        "class_name": class_name,
        "major": meta.get("major") or "",
        "department": meta.get("department") or "",
        "grade": meta.get("grade") or "",
        "student_count": meta.get("student_count") or 0,
        "academic_year": meta.get("academic_year") or "",
        "semester": meta.get("semester") or "",
    }


def _build_teaching_tasks(
    class_name: str,
    task_batch: str,
    courses: list[dict[str, Any]],
    details_by_code: dict[str, CourseDetail],
    occurrences: list[Occurrence],
) -> list[dict[str, Any]]:
    rows = []
    occurrence_codes = {item.course_code for item in occurrences}
    for course in courses:
        code = str(course["course_code"])
        if code not in occurrence_codes and code not in details_by_code:
            continue
        detail = details_by_code.get(code)
        teacher = detail.teachers[0] if detail and detail.teachers else ""
        rows.append({
            "course_code": code,
            "course_name": course["course_name"],
            "teacher_name": teacher,
            "class_name": class_name,
            "total_hours": course["required_hours"],
            "required_room_type": course["required_room_type"],
            "task_batch": task_batch,
            "schedulable": course["schedulable"],
            "exclude_reason": course["exclude_reason"],
            "source": "schedule_excel",
        })
    return rows


def _occurrence_row(item: Occurrence, details_by_code: dict[str, CourseDetail]) -> dict[str, Any]:
    detail = details_by_code.get(item.course_code)
    return {
        "class_name": item.class_name,
        "course_code": item.course_code,
        "course_name": detail.course_name if detail else item.course_code,
        "teacher_name": detail.teachers[0] if detail and detail.teachers else "",
        "classroom_name": item.classroom_name,
        "day_of_week": item.day_of_week,
        "period_index": item.period_index,
        "row_index": item.row_index,
        "col_index": item.col_index,
        "sheet_name": item.sheet_name,
        "raw_cell": item.raw_cell,
    }


def _ordered_codes(occurrences: list[Occurrence], details_by_code: dict[str, CourseDetail]) -> list[str]:
    result: list[str] = []
    seen = set()
    for item in occurrences:
        if item.course_code not in seen:
            seen.add(item.course_code)
            result.append(item.course_code)
    for code in details_by_code:
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _infer_course_type(course_name: str, rooms: list[str]) -> str:
    if any(keyword in course_name for keyword in ["实验", "上机", "实训", "程序设计", "数据库应用"]):
        return "上机课"
    if rooms and any(room.startswith(("9", "8")) for room in rooms):
        return "上机课"
    return "理论课"


def _required_room_type(course_type: str, schedulable: bool) -> str:
    if not schedulable:
        return ""
    return "机房" if course_type == "上机课" else "普通教室"


def _schedulable_state(course_code: str, course_name: str) -> tuple[bool, str]:
    if course_code in UNSCHEDULABLE_COURSES or course_name in UNSCHEDULABLE_COURSES:
        return False, "公共体育暂不进入当前排课引擎"
    return True, ""


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _split_list(value: str) -> list[str]:
    return [_clean_token(item) for item in re.split(r"[,，、/;；\s]+", value or "") if _clean_token(item)]


def _clean_course_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip(" ，,;；")


def _clean_token(value: str) -> str:
    return str(value or "").strip().strip("，,;；:：")


def _infer_grade(class_name: str) -> str:
    match = re.search(r"(20\d{2})级", class_name or "")
    return match.group(1) if match else ""


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _col_to_index(col: str) -> int:
    result = 0
    for char in col:
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse one class schedule .xlsx into CSV files.")
    parser.add_argument("--input", required=True, help="Path to .xlsx class schedule file")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--class-name", default=None)
    parser.add_argument("--major", default=None)
    parser.add_argument("--department", default=None)
    parser.add_argument("--grade", default=None)
    parser.add_argument("--student-count", type=int, default=None)
    parser.add_argument("--task-batch", default="DEFAULT")
    args = parser.parse_args()
    report = parse_schedule_excel(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        class_name=args.class_name,
        major=args.major,
        department=args.department,
        grade=args.grade,
        student_count=args.student_count,
        task_batch=args.task_batch,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
