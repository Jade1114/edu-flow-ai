"""V2 排课集成入口 — generate_v2()

将教师交叉度分类 + 模板生成 + 教室排序 + Beam Search 构造
整合为一条可直接替换旧 _run_generation() 的完整管线。

用法:
    from ml.channels.integration import generate_v2
    
    result = generate_v2(tasks, classrooms, time_slots)
    # result = {"success": True, "assignments": [...], "total_score": ...}
"""

from __future__ import annotations

import logging

try:
    from ml.channels.teacher_classifier import classify_teachers
    from ml.channels.beam_constructor import construct_timetable
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.channels.teacher_classifier import classify_teachers
    from ml.channels.beam_constructor import construct_timetable

_log = logging.getLogger("v2")


def generate_v2(
    tasks: list[dict],
    classrooms: list[dict],
    time_slots: list[dict],
    beam_width: int = 3,
    high_cross_threshold: int = 12,
) -> dict:
    """V2 排课入口 — 替代旧 GA generate_scheme()。

    Args:
        tasks: 教学任务列表
        classrooms: 教室列表
        time_slots: 时间段列表
        beam_width: Beam Search 宽度（默认3）
        high_cross_threshold: 高交叉教师阈值（默认跨12班以上）

    Returns:
        {"success": True/False,
         "assignments": [...],
         "total_score": 0.0,
         "unassigned": [...],
         "stats": {...}}
    """
    # 1. 字段统一（classifier 用 teacher，constructor 用 teacher_name）
    for t in tasks:
        if "teacher_name" not in t or not t["teacher_name"]:
            t["teacher_name"] = str(t.get("teacher_id", "?"))
        t["teacher"] = t["teacher_name"]

    # 2. 教师交叉度分析
    classification = classify_teachers(tasks, threshold=high_cross_threshold)
    high_cross = set(classification["high_cross"])
    stats = classification["stats"]

    _log.info("V2: %d tasks, %d high-cross teachers (threshold=%d)",
              len(tasks), stats["high_cross_count"], high_cross_threshold)
    _log.info("  High-cross teachers: %s", high_cross)

    # 3. Beam Search 构造
    result = construct_timetable(
        tasks=tasks,
        classrooms=classrooms,
        time_slots=time_slots,
        beam_width=beam_width,
        teacher_priority=list(high_cross),
    )

    # 4. 补充统计
    if result.get("success"):
        assigned_count = len(result.get("assignments", []))
        unassigned_count = len(result.get("unassigned", []))
        result["stats"].update({
            "v2_mode": True,
            "high_cross_teachers": stats["high_cross_count"],
            "total_tasks": len(tasks),
            "assigned": assigned_count,
            "unassigned": unassigned_count,
            "assign_rate": round(assigned_count / max(1, len(tasks)) * 100, 1),
            "beam_width": beam_width,
        })
        _log.info("V2 done: %d/%d assigned (%.1f%%), score=%.2f",
                  assigned_count, len(tasks),
                  assigned_count / max(1, len(tasks)) * 100,
                  result.get("total_score", 0))
    else:
        _log.error("V2 FAILED: %s", result.get("error", "unknown"))

    return result


# ── 快速验证 ─────────────────────────────────────────
if __name__ == "__main__":
    import json
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
    tasks_raw = [json.loads(l) for l in (DATA / "teaching_tasks.jsonl").read_text().splitlines() if l.strip()]
    classrooms_raw = [json.loads(l) for l in (DATA / "classrooms.jsonl").read_text().splitlines() if l.strip()]

    # 测试：2023级软件工程2班
    cg = "2023级软件工程2班"
    sample = [t for t in tasks_raw if t["class_group"] == cg][:10]

    alloc_tasks = []
    for tt in sample:
        alloc_tasks.append({
            "id": abs(hash(cg + tt["course_code"])) % 100000 + 1,
            "teacher_id": abs(hash(tt["teacher"])) % 10000 + 1,
            "teacher_name": tt["teacher"],
            "total_lessons": max(1, int(tt["total_hours"] / 2)),
            "total_hours": int(tt["total_hours"]),
            "required_room_type": "",
            "class_group_ids": [abs(hash(cg)) % 10000 + 1],
            "student_count": 46,
            "course_name": tt.get("course_name", ""),
            "course_code": tt.get("course_code", ""),
        })

    classrooms = [{"id": i + 1, "name": cr["name"], "capacity": 80, "classroom_type": cr.get("classroom_type", "")}
                  for i, cr in enumerate(classrooms_raw[:50])]

    time_slots = [{"id": w * 100 + d * 10 + p, "week_number": w, "day_of_week": d, "period_index": p}
                  for w in range(1, 19) for d in range(1, 6) for p in range(1, 6)]

    print("\n" + "=" * 50)
    print("📊 V2 集成测试: 2023级软件工程2班")
    print("=" * 50)

    result = generate_v2(alloc_tasks, classrooms, time_slots, beam_width=2)

    if result["success"]:
        print(f"\n  ✅ 成功安排 {result['stats']['assigned']}/{result['stats']['total_tasks']}")
        print(f"  安排率: {result['stats']['assign_rate']}%")
        print(f"  总评分: {result['total_score']:.2f}")
        print(f"  未安排: {result['stats']['unassigned']} 个")
        print("\n  📅 课表摘要:")
        for a in result["assignments"]:
            print(f"    周{a['week_number']} 周{a['day_of_week']} 第{a['period_index']}节 "
                  f"{a.get('teacher_name', '?'):8s} "
                  f"教室={a.get('room_name', '?'):5s} "
                  f"评分={a.get('placement_score', 0):.2f}")
    else:
        print(f"\n  ❌ 失败: {result.get('error')}")
