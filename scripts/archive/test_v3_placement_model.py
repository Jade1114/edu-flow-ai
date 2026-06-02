"""Smoke-test the V3 placement model with 10 preset teaching-task identities.

Input contract:
  course_name + teacher_no + teacher_name + class_name

Output:
  JSONL rows with TopK resources: day_of_week + period_index + classroom.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "v3"
MODEL_PATH = MODEL_DIR / "placement_model.txt"
SCHEMA_PATH = MODEL_DIR / "placement_model_schema.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "generated" / "v3" / "placement_model_smoke_test.jsonl"

DAY_PERIODS = [(day, period) for day in range(1, 6) for period in range(1, 6)]
ALLOWED_CLASSROOM_TYPES = frozenset({"普通教室", "机房"})

PRESET_INPUTS = [
    {"course_name": "产品设计综合训练", "teacher_no": "TEACHER_李伟", "teacher_name": "李伟", "class_name": "2022级产品设计1班"},
    {"course_name": "产品摄影", "teacher_no": "TEACHER_刘瑶", "teacher_name": "刘瑶", "class_name": "2022级产品设计1班"},
    {"course_name": "专业素质拓展", "teacher_no": "TEACHER_张煜", "teacher_name": "张煜", "class_name": "2022级产品设计1班"},
    {"course_name": "产品设计综合训练", "teacher_no": "TEACHER_王庆莲", "teacher_name": "王庆莲", "class_name": "2022级产品设计2班"},
    {"course_name": "产品摄影", "teacher_no": "TEACHER_温乔", "teacher_name": "温乔", "class_name": "2022级产品设计2班"},
    {"course_name": "渲染", "teacher_no": "TEACHER_张玮", "teacher_name": "张玮", "class_name": "2022级人工智能1班"},
    {"course_name": "体系结构与编程", "teacher_no": "TEACHER_严南", "teacher_name": "严南", "class_name": "2022级通信工程1班"},
    {"course_name": "游戏开发实训", "teacher_no": "TEACHER_万玉梅", "teacher_name": "万玉梅", "class_name": "2022级软件工程1班"},
    {"course_name": "应用技术", "teacher_no": "TEACHER_于佳", "teacher_name": "于佳", "class_name": "2022级休闲体育3班"},
    {"course_name": "技术", "teacher_no": "TEACHER_乔于轩", "teacher_name": "乔于轩", "class_name": "2022级产品设计3班"},
]


def run(*, top_k: int = 10, output_path: Path = OUTPUT_PATH) -> Path:
    if not MODEL_PATH.exists() or not SCHEMA_PATH.exists():
        raise FileNotFoundError("V3 placement model is missing. Train it before running smoke tests.")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    features = schema["features"]
    model = lgb.Booster(model_file=str(MODEL_PATH))
    courses_by_name = _by_key(_read_jsonl(DATA_DIR / "courses.jsonl"), "name")
    class_groups_by_name = _by_key(_read_jsonl(DATA_DIR / "class_groups.jsonl"), "name")
    classrooms = [
        row for row in _read_jsonl(DATA_DIR / "classrooms.jsonl")
        if _is_supported_classroom(row)
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for preset in PRESET_INPUTS:
            resources = _rank_resources(
                preset,
                courses_by_name=courses_by_name,
                class_groups_by_name=class_groups_by_name,
                classrooms=classrooms,
                model=model,
                features=features,
                top_k=top_k,
            )
            row = {
                "input": preset,
                "resources": resources,
                "meta": {
                    "top_k": top_k,
                    "candidate_count": len(classrooms) * len(DAY_PERIODS),
                    "model_path": str(MODEL_PATH),
                },
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return output_path


def _rank_resources(
    preset: dict[str, str],
    *,
    courses_by_name: dict[str, dict[str, Any]],
    class_groups_by_name: dict[str, dict[str, Any]],
    classrooms: list[dict[str, Any]],
    model,
    features: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    course = courses_by_name.get(preset["course_name"]) or {}
    class_group = class_groups_by_name.get(preset["class_name"]) or {}
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for classroom in classrooms:
        if not _room_feasible(course, classroom):
            continue
        for day, period in DAY_PERIODS:
            candidate = {
                **preset,
                "course_code": str(course.get("code") or ""),
                "class_major": str(class_group.get("major") or ""),
                "class_department": str(class_group.get("department") or ""),
                "class_grade": str(class_group.get("grade") or ""),
                "class_no": _extract_class_no(preset["class_name"]),
                "student_count": _safe_float(class_group.get("student_count")),
                "total_hours": _safe_float(course.get("hours")),
                "course_type": str(course.get("course_type") or ""),
                "required_room_type": _required_room_type(course),
                "day_of_week": day,
                "period_index": period,
                "classroom_name": str(classroom.get("name") or ""),
                "classroom_type": str(classroom.get("classroom_type") or ""),
                "classroom_capacity": _safe_float(classroom.get("capacity")),
            }
            student_count = candidate["student_count"]
            capacity = candidate["classroom_capacity"]
            candidate["capacity_margin"] = capacity - student_count
            candidate["capacity_ratio"] = student_count / max(1.0, capacity)
            candidate["is_room_type_match"] = int(_norm(candidate["required_room_type"]) == _norm(candidate["classroom_type"])) if candidate["required_room_type"] else 0
            candidates.append(candidate)
            rows.append(_features(candidate))

    frame = pd.DataFrame(rows, columns=features)
    scores = model.predict(frame)
    ranked = sorted(zip(candidates, scores), key=lambda item: float(item[1]), reverse=True)
    return [
        {
            "rank": rank,
            "slot": {
                "day_of_week": int(candidate["day_of_week"]),
                "period_index": int(candidate["period_index"]),
            },
            "classroom": {
                "name": candidate["classroom_name"],
                "type": candidate["classroom_type"],
                "capacity": int(candidate["classroom_capacity"]),
            },
            "score": round(float(score), 6),
        }
        for rank, (candidate, score) in enumerate(ranked[:top_k], start=1)
    ]


def _features(row: dict[str, Any]) -> dict[str, float]:
    encoded = {
        "course_name_code": _stable_code(row.get("course_name")),
        "course_code_code": _stable_code(row.get("course_code")),
        "teacher_no_code": _stable_code(row.get("teacher_no")),
        "teacher_name_code": _stable_code(row.get("teacher_name")),
        "class_name_code": _stable_code(row.get("class_name")),
        "class_major_code": _stable_code(row.get("class_major")),
        "class_department_code": _stable_code(row.get("class_department")),
        "course_type_code": _stable_code(row.get("course_type")),
        "required_room_type_code": _stable_code(row.get("required_room_type")),
        "classroom_name_code": _stable_code(row.get("classroom_name")),
        "classroom_type_code": _stable_code(row.get("classroom_type")),
    }
    numeric = {
        "class_grade": _safe_float(row.get("class_grade")),
        "class_no": _safe_float(row.get("class_no")),
        "student_count": _safe_float(row.get("student_count")),
        "total_hours": _safe_float(row.get("total_hours")),
        "day_of_week": _safe_float(row.get("day_of_week")),
        "period_index": _safe_float(row.get("period_index")),
        "classroom_capacity": _safe_float(row.get("classroom_capacity")),
        "capacity_margin": _safe_float(row.get("capacity_margin")),
        "capacity_ratio": _safe_float(row.get("capacity_ratio")),
        "is_room_type_match": _safe_float(row.get("is_room_type_match")),
    }
    return {**encoded, **numeric}


def _required_room_type(course: dict[str, Any]) -> str:
    explicit = str(course.get("required_room_type") or "").strip()
    if explicit:
        return explicit
    return {"理论课": "普通教室", "上机课": "机房"}.get(str(course.get("course_type") or "").strip(), "")


def _room_feasible(course: dict[str, Any], classroom: dict[str, Any]) -> bool:
    if not _is_supported_classroom(classroom):
        return False
    required = _norm(_required_room_type(course))
    room_type = _norm(classroom.get("classroom_type"))
    return not required or required == room_type


def _is_supported_classroom(classroom: dict[str, Any]) -> bool:
    room_type = str(classroom.get("classroom_type") or "").strip()
    name = str(classroom.get("name") or "").strip().lower()
    if room_type not in ALLOWED_CLASSROOM_TYPES:
        return False
    if name.startswith("xn") or name.startswith("虚拟"):
        return False
    return "操场" not in name and "体育" not in name


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or "").strip(): row for row in rows if str(row.get(key) or "").strip()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def _stable_code(value: Any, modulo: int = 10007) -> float:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return 0.0
    total = 0
    for char in text:
        total = (total * 131 + ord(char)) % modulo
    return float(total + 1)


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
    parser = argparse.ArgumentParser(description="Run V3 placement model smoke test.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    output = run(top_k=max(1, args.top_k), output_path=Path(args.output))
    print(output)


if __name__ == "__main__":
    main()
