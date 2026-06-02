"""Smoke-test the V3 direct placement model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.scheduling_v3.placement_direct import DirectPlacementModel, DIRECT_MODEL_PATH, parse_resource_key

DATA_DIR = PROJECT_ROOT / "data" / "real-dataset"
OUTPUT_PATH = PROJECT_ROOT / "ml" / "data" / "generated" / "v3" / "placement_direct_smoke_test.jsonl"
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
    model = DirectPlacementModel.load()
    courses_by_name = _by_key(_read_jsonl(DATA_DIR / "courses.jsonl"), "name")
    class_groups_by_name = _by_key(_read_jsonl(DATA_DIR / "class_groups.jsonl"), "name")
    classrooms_by_name = _by_key(_read_jsonl(DATA_DIR / "classrooms.jsonl"), "name")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for preset in PRESET_INPUTS:
            task_like = _task_like(preset, courses_by_name, class_groups_by_name)
            resources = []
            for resource_key, score in model.predict_topk(task_like, top_k=top_k * 3):
                parsed = parse_resource_key(resource_key)
                if parsed is None:
                    continue
                room_name, day, period = parsed
                classroom = classrooms_by_name.get(room_name)
                if not classroom or not _is_supported_classroom(classroom) or not _room_feasible(task_like, classroom):
                    continue
                resources.append({
                    "rank": len(resources) + 1,
                    "slot": {"day_of_week": day, "period_index": period},
                    "classroom": {
                        "name": room_name,
                        "type": classroom.get("classroom_type") or "",
                        "capacity": int(classroom.get("capacity") or 0),
                    },
                    "score": round(float(score), 6),
                    "resource_key": resource_key,
                })
                if len(resources) >= top_k:
                    break
            handle.write(json.dumps({
                "input": preset,
                "resources": resources,
                "meta": {"top_k": top_k, "model_path": str(DIRECT_MODEL_PATH)},
            }, ensure_ascii=False) + "\n")
    return output_path


def _task_like(
    preset: dict[str, str],
    courses_by_name: dict[str, dict[str, Any]],
    class_groups_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    course = courses_by_name.get(preset["course_name"]) or {}
    class_group = class_groups_by_name.get(preset["class_name"]) or {}
    return {
        **preset,
        "course_code": course.get("code") or "",
        "class_major": class_group.get("major") or "",
        "class_department": class_group.get("department") or "",
        "class_grade": class_group.get("grade") or "",
        "student_count": class_group.get("student_count") or 0,
        "total_hours": course.get("hours") or 0,
        "course_type": course.get("course_type") or "",
        "required_room_type": course.get("required_room_type") or "",
    }


def _is_supported_classroom(classroom: dict[str, Any]) -> bool:
    room_type = str(classroom.get("classroom_type") or "").strip()
    name = str(classroom.get("name") or "").strip().lower()
    if room_type not in ALLOWED_CLASSROOM_TYPES:
        return False
    if name.startswith("xn") or name.startswith("虚拟"):
        return False
    return "操场" not in name and "体育" not in name


def _room_feasible(task_like: dict[str, Any], classroom: dict[str, Any]) -> bool:
    required = _norm(task_like.get("required_room_type"))
    room_type = _norm(classroom.get("classroom_type"))
    return not required or required == room_type


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


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or "").strip(): row for row in rows if str(row.get(key) or "").strip()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test V3 direct placement model.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    print(run(top_k=args.top_k, output_path=Path(args.output)))


if __name__ == "__main__":
    main()
