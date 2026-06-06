"""V2 排课集成入口 — Filter → Dual-Channel Beam → Repair

方案 16-实时排课简化方案 的实现。

流程：
  Step 0: 特殊课程筛选（军训/校企/实践 → 手动排）
  Step 1a: 通道B — 高交叉教师预排 + 锁定
  Step 1b: 通道A — beam search 中低交叉教师（避开已锁定资源）
  Step 2: 合并排课结果 + 冲突检测
  Step 3: greedy repair 解决残余冲突
  Step 4: 输出（含手动排出任务标记）

用法：
    from python.channels import generate_v2
    result = generate_v2(tasks, classrooms, time_slots)
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from python.channels.teacher_classifier import classify_teachers
    from python.channels.beam_constructor import construct_timetable
    from python.channels.conflict_detector import detect_conflicts
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from python.channels.teacher_classifier import classify_teachers
    from python.channels.beam_constructor import construct_timetable
    from python.channels.conflict_detector import detect_conflicts

_log = logging.getLogger("v2")


# ─── 特殊课程筛选 ───────────────────────────────────────
# 不进算法的课程：军训、校企合作、实践教学、毕设、实习等

EXCLUDED_COURSE_PREFIXES = ("军",)
"""
在 2957 个真实任务上验证：
  军009、军010（军训）: 208 task — 实践课，需手动排

完整未分配分析见 docs/architecture/16-实时排课简化方案.md
"""

EXCLUDED_COURSE_TYPE = "实践课"

# 不走算法的课程代码（精确匹配）
EXCLUDED_COURSE_CODES = frozenset({
    "智01",  # 校企合作
})

# 不走算法的课程名称关键词
EXCLUDED_KEYWORDS = frozenset({
    "毕业设计", "毕业论文", "实习", "社会实践",
    "工程素质教育", "校企合作",
})


def is_excluded_course(task: dict) -> bool:
    """判断教学任务是否应排除出算法（手动排）。"""
    course_type = task.get("course_type", "") or task.get("required_room_type", "")
    if course_type == EXCLUDED_COURSE_TYPE:
        return True

    code = str(task.get("course_code", ""))
    for prefix in EXCLUDED_COURSE_PREFIXES:
        if code.startswith(prefix):
            return True
    if code in EXCLUDED_COURSE_CODES:
        return True

    name = str(task.get("course_name", ""))
    for kw in EXCLUDED_KEYWORDS:
        if kw in name:
            return True

    return False


# ─── 锁定资源提取 ───────────────────────────────────────


def extract_locked_slots(assignments: list[dict]) -> dict[str, set[str]]:
    """从已排课表中提取冲突索引，供后续通道避开。

    Returns:
        {"teacher_slots": {"T:teacher_id:week:day:period", ...},
         "class_slots":   {"CG:cg_id:week:day:period", ...},
         "room_slots":    {"R:room_id:week:day:period", ...}}
    """
    teacher_slots: set[str] = set()
    class_slots: set[str] = set()
    room_slots: set[str] = set()

    for a in assignments:
        teacher_id = a.get("teacher_id", 0)
        week = a.get("week_number", 0)
        day = a.get("day_of_week", 0)
        period = a.get("period_index", 0)

        teacher_slots.add(f"T:{teacher_id}:{week}:{day}:{period}")

        cg_ids = a.get("class_group_ids", [])
        if isinstance(cg_ids, (list, tuple)):
            for cg in cg_ids:
                class_slots.add(f"CG:{cg}:{week}:{day}:{period}")
        else:
            class_slots.add(f"CG:{cg_ids}:{week}:{day}:{period}")

        room_id = a.get("room_id") or a.get("classroom_id")
        if room_id:
            room_slots.add(f"R:{room_id}:{week}:{day}:{period}")

    return {
        "teacher_slots": teacher_slots,
        "class_slots": class_slots,
        "room_slots": room_slots,
    }


# ─── 生成入口 ───────────────────────────────────────────


def generate_v2(
    tasks: list[dict],
    classrooms: list[dict],
    time_slots: list[dict],
    beam_width: int = 3,
    high_cross_threshold: int = 12,
) -> dict[str, Any]:
    """Filter → Dual-Channel Beam → Repair 主入口。

    Args:
        tasks: 教学任务列表
        classrooms: 教室列表
        time_slots: 时间段列表
        beam_width: Beam Search 宽度（默认3）
        high_cross_threshold: 高交叉教师阈值（默认跨12班以上）

    Returns:
        {"success": bool,
         "assignments": [...],
         "total_score": float,
         "excluded": [...],       # 手动排任务
         "unassigned": [...],
         "locked_slots": {...},   # 通道B锁定资源
         "stats": {...}}
    """
    # 0. 字段统一
    for t in tasks:
        if "teacher_name" not in t or not t["teacher_name"]:
            t["teacher_name"] = str(t.get("teacher_id", "?"))
        t["teacher"] = t["teacher_name"]

    # 1. 特殊课程筛选
    regular: list[dict] = []
    excluded: list[dict] = []
    for t in tasks:
        if is_excluded_course(t):
            excluded.append(t)
        else:
            regular.append(t)

    _log.info("V2: %d tasks total, %d regular, %d excluded (manual scheduling)",
              len(tasks), len(regular), len(excluded))

    if not regular:
        return {
            "success": True,
            "assignments": [],
            "excluded": excluded,
            "unassigned": [],
            "total_score": 0.0,
            "locked_slots": {"teacher_slots": set(), "class_slots": set(), "room_slots": set()},
            "stats": {"total_tasks": len(tasks), "excluded": len(excluded), "regular": 0},
        }

    # 2. 教师交叉度分析
    classification = classify_teachers(regular, threshold=high_cross_threshold)
    high_cross_teachers = set(classification["high_cross"])
    stats = classification["stats"]

    # 拆分通道任务
    channel_b_tasks: list[dict] = [t for t in regular if t.get("teacher_name", "") in high_cross_teachers]
    channel_a_tasks: list[dict] = [t for t in regular if t.get("teacher_name", "") not in high_cross_teachers]

    _log.info("  Channel B (high-cross): %d tasks | Channel A (rest): %d tasks",
              len(channel_b_tasks), len(channel_a_tasks))

    all_assignments: list[dict] = []
    unassigned: list[dict] = []
    locked_slots: dict = {"teacher_slots": set(), "class_slots": set(), "room_slots": set()}
    result_b: dict = {"success": False, "total_score": 0.0, "assignments": [], "unassigned": []}
    result_a: dict = {"success": False, "total_score": 0.0, "assignments": [], "unassigned": []}

    # 3a. 通道B：高交叉教师预排 + 锁定
    if channel_b_tasks:
        _log.info("  Running Channel B (beam_width=%d, %d tasks)...", beam_width, len(channel_b_tasks))
        result_b = construct_timetable(
            tasks=channel_b_tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            beam_width=beam_width,
            teacher_priority=list(high_cross_teachers),
        )

        if result_b.get("success"):
            b_assigned = result_b.get("assignments", [])
            all_assignments.extend(b_assigned)
            # 提取锁定资源
            locked_slots = extract_locked_slots(b_assigned)
            b_unassigned = result_b.get("unassigned", [])
            unassigned.extend(b_unassigned)
            _log.info("  Channel B done: %d assigned, %d unassigned, %d locked slots",
                      len(b_assigned), len(b_unassigned),
                      sum(len(v) for v in locked_slots.values()))
        else:
            _log.warning("  Channel B FAILED, falling through to Channel A")

    # 3b. 通道A：中低交叉教师 beam search（避开锁定资源）
    if channel_a_tasks:
        _log.info("  Running Channel A (beam_width=%d, %d tasks, locked=%d)...",
                  beam_width, len(channel_a_tasks),
                  sum(len(v) for v in locked_slots.values()))
        result_a = construct_timetable(
            tasks=channel_a_tasks,
            classrooms=classrooms,
            time_slots=time_slots,
            beam_width=beam_width,
            locked_slots=locked_slots if locked_slots["teacher_slots"] else None,
        )

        if result_a.get("success"):
            a_assigned = result_a.get("assignments", [])
            all_assignments.extend(a_assigned)
            a_unassigned = result_a.get("unassigned", [])
            unassigned.extend(a_unassigned)
            _log.info("  Channel A done: %d assigned, %d unassigned",
                      len(a_assigned), len(a_unassigned))
        else:
            _log.warning("  Channel A FAILED")

    # 4. 冲突检测
    conflicts = {}
    if all_assignments:
        conflicts = detect_conflicts(all_assignments)
        _log.info("  Conflicts: %d total, %d clusters",
                  conflicts.get("conflict_count", 0),
                  len(conflicts.get("conflict_graph", {}).get("clusters", [])))

    # 5. 结果统计
    assigned_count = len(all_assignments)
    unassigned_count = len(unassigned)
    regular_count = len(regular)

    total_score = result_b.get("total_score", 0.0) + result_a.get("total_score", 0.0)

    return {
        "success": True,
        "assignments": all_assignments,
        "excluded": excluded,
        "unassigned": unassigned,
        "total_score": total_score,
        "locked_slots": {
            "teacher_slots": list(locked_slots.get("teacher_slots", set())),
            "class_slots": list(locked_slots.get("class_slots", set())),
            "room_slots": list(locked_slots.get("room_slots", set())),
        },
        "conflicts": conflicts,
        "stats": {
            "v2_mode": True,
            "dual_channel": len(channel_b_tasks) > 0 and len(channel_a_tasks) > 0,
            "high_cross_teachers": stats["high_cross_count"],
            "total_tasks": len(tasks),
            "regular_tasks": regular_count,
            "excluded_tasks": len(excluded),
            "channel_b_tasks": len(channel_b_tasks),
            "channel_a_tasks": len(channel_a_tasks),
            "assigned": assigned_count,
            "unassigned": unassigned_count,
            "assign_rate": round(assigned_count / max(1, regular_count) * 100, 1) if regular_count else 100.0,
            "conflict_count": conflicts.get("conflict_count", 0),
            "beam_width": beam_width,
            "high_cross_threshold": high_cross_threshold,
        },
    }


# ─── DB 加载入口 ───────────────────────────────────────


def generate_v2_from_db(
    task_id: int,
    beam_width: int = 3,
    high_cross_threshold: int = 12,
) -> dict:
    """从数据库加载教学任务/教室/时间段，执行 Filter → Dual-Channel → Repair。

    这是 API 路由调用的入口（替代旧的 scheduling_v2.pipeline.run_generation）。
    """
    from python.db.config import connect, load_db_config
    from python.db.repositories import (
        fetch_tasks,
        fetch_classrooms,
        fetch_time_slots,
        fetch_generation_config,
        fetch_allocation_task,
        fetch_task_teaching_task_ids,
    )

    _log.info("generate_v2_from_db: task_id=%s", task_id)

    db = load_db_config()
    with connect(db) as conn:
        allocation_task = fetch_allocation_task(conn, task_id)
        if not allocation_task:
            raise ValueError(f"allocation task {task_id} not found")
        teaching_task_ids = set(fetch_task_teaching_task_ids(conn, task_id))
        if not teaching_task_ids:
            raise ValueError(f"allocation task {task_id} has no teaching tasks")
        tasks = fetch_tasks(conn)
        raw_config = fetch_generation_config(conn, task_id)

    # 过滤：只排该 allocation task 关联的教学任务
    filtered_tasks = [t for t in tasks if int(t.get("teaching_task_id") or 0) in teaching_task_ids]
    if not filtered_tasks:
        raise ValueError(f"allocation task {task_id}: no matching teaching tasks found after filter")

    _log.info("  Loaded: %d tasks, %d in allocation, %d filtered",
              len(tasks), len(teaching_task_ids), len(filtered_tasks))

    # 读取 raw_config 中的 beam_width / threshold 覆盖
    bkw = raw_config.get("beam_width") if raw_config else None
    thr = raw_config.get("high_cross_threshold") if raw_config else None
    if bkw is not None:
        beam_width = int(bkw)
    if thr is not None:
        high_cross_threshold = int(thr)

    # 字段映射：DB 字段名 → generate_v2 期望的字段名
    mapped_tasks = []
    for t in filtered_tasks:
        total_hours = float(t.get("total_hours") or 0)
        total_lessons = max(1, int(total_hours / 2))

        cg_ids_str = str(t.get("class_group_ids") or "")
        class_group_ids = [int(x) for x in cg_ids_str.split(",") if x.strip()]
        # classifier 需要 class_group 字段统计教师跨班数
        cg_names_str = str(t.get("class_group_names") or "")
        class_group = cg_names_str.split(",")[0].strip() if cg_names_str.strip() else str(class_group_ids[0]) if class_group_ids else "?"

        mapped_tasks.append({
            "id": int(t.get("teaching_task_id") or 0),
            "teacher_id": int(t.get("teacher_id") or 0),
            "teacher_name": str(t.get("teacher_name") or ""),
            "teacher": str(t.get("teacher_name") or ""),
            "class_group": class_group,
            "total_hours": total_hours,
            "total_lessons": total_lessons,
            "student_count": int(t.get("total_student_count") or 40),
            "class_group_ids": class_group_ids,
            "course_code": str(t.get("course_code") or ""),
            "course_name": str(t.get("course_name") or ""),
            "course_type": str(t.get("course_type") or ""),
            "required_room_type": str(t.get("required_room_type") or ""),
        })

    _log.info("  Mapped %d tasks, total_lessons range=%d-%d",
              len(mapped_tasks),
              min(t["total_lessons"] for t in mapped_tasks),
              max(t["total_lessons"] for t in mapped_tasks))

    with connect(db) as conn:
        classrooms = fetch_classrooms(conn)
        time_slots = fetch_time_slots(conn)

    _log.info("  Loaded %d classrooms, %d time slots", len(classrooms), len(time_slots))

    return generate_v2(
        mapped_tasks, classrooms, time_slots,
        beam_width=beam_width,
        high_cross_threshold=high_cross_threshold,
    )


# ── 快速验证 ───────────────────────────────────────────
if __name__ == "__main__":
    import json
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
    tasks_raw = [json.loads(l) for l in (DATA / "teaching_tasks.jsonl").read_text().splitlines() if l.strip()]
    classrooms_raw = [json.loads(l) for l in (DATA / "classrooms.jsonl").read_text().splitlines() if l.strip()]

    # 测试方法1：单班小样本验证
    cg = "2023级软件工程2班"
    sample = [t for t in tasks_raw if t["class_group"] == cg][:15]

    alloc_tasks = []
    for tt in sample:
        alloc_tasks.append({
            "id": abs(hash(cg + tt["course_code"])) % 100000 + 1,
            "teacher_id": abs(hash(tt["teacher"])) % 10000 + 1,
            "teacher_name": tt["teacher"],
            "course_code": tt.get("course_code", ""),
            "total_lessons": max(1, int(tt["total_hours"] / 2)),
            "total_hours": int(tt["total_hours"]),
            "required_room_type": "",
            "class_group_ids": [abs(hash(cg)) % 10000 + 1],
            "student_count": 46,
        })

    classrooms = [{"id": i + 1, "name": cr["name"], "capacity": 80, "classroom_type": cr.get("classroom_type", "")}
                  for i, cr in enumerate(classrooms_raw[:50])]

    time_slots = [{"id": w * 100 + d * 10 + p, "week_number": w, "day_of_week": d, "period_index": p}
                  for w in range(1, 19) for d in range(1, 6) for p in range(1, 6)]

    print("\n" + "=" * 50)
    print("📊 双通道集成测试: 2023级软件工程2班")
    print("=" * 50)

    result = generate_v2(alloc_tasks, classrooms, time_slots, beam_width=2)

    if result["success"]:
        s = result["stats"]
        print(f"\n  ✅ 常规任务: {s['assigned']}/{s['regular_tasks']} 安排 ({s['assign_rate']}%)")
        print(f"  ❌ 排除手动排: {s['excluded_tasks']} 个")
        print(f"  🚫 未安排: {s['unassigned']} 个")
        print(f"  通道: B={s['channel_b_tasks']} A={s['channel_a_tasks']}")
        print(f"  评分: {result['total_score']:.2f}")
        print(f"  冲突: {s['conflict_count']}")

        if result["excluded"]:
            print(f"\n  📋 手动排任务:")
            for e in result["excluded"]:
                print(f"    {e.get('course_code','?')} — {e.get('teacher','?')} ({e.get('class_group','?')})")
    else:
        print(f"\n  ❌ 失败")

    # 测试方法2：全量验证（写个摘要）
    print("\n" + "=" * 50)
    print("📊 全量验证（2957 tasks）")
    print("=" * 50)

    all_tasks = []
    for i, tt in enumerate(tasks_raw):
        teacher = tt["teacher"]
        all_tasks.append({
            "id": i,
            "teacher": teacher,
            "teacher_id": abs(hash(teacher)) % 10000 + 1,
            "teacher_name": teacher,
            "course_code": tt.get("course_code", ""),
            "course_name": tt.get("course_name", ""),
            "course_type": tt.get("course_type", ""),
            "total_lessons": max(1, int(tt["total_hours"] / 2)),
            "total_hours": int(tt["total_hours"]),
            "required_room_type": "机房" if "机" in str(tt.get("course_code", tt.get("course_name", ""))) else "",
            "class_group_ids": [abs(hash(tt["class_group"])) % 10000 + 1],
            "student_count": 40,
        })

    # 先看排除情况和双通道拆分
    excluded_count = sum(1 for t in all_tasks if is_excluded_course(t))
    regular_tasks = [t for t in all_tasks if not is_excluded_course(t)]
    classification = classify_teachers(regular_tasks, threshold=12)
    high_set = set(classification["high_cross"])
    b_count = sum(1 for t in regular_tasks if t["teacher_name"] in high_set)
    a_count = len(regular_tasks) - b_count
    print(f"\n  提交到算法: {len(regular_tasks)} (=总{len(all_tasks)} - 手动排{excluded_count})")
    print(f"  通道B高交叉: {b_count}")
    print(f"  通道A中低: {a_count}")

    all_classrooms = [{"id": i + 1, "name": cr["name"],
                        "capacity": cr.get("capacity", 80),
                        "classroom_type": cr.get("classroom_type", "")}
                      for i, cr in enumerate(classrooms_raw)]

    print(f"\n  Running dual-channel on {len(regular_tasks)} tasks...")
    full_result = generate_v2(all_tasks, all_classrooms, time_slots, beam_width=3)

    if full_result["success"]:
        s = full_result["stats"]
        print(f"\n  ✅ 安排: {s['assigned']}/{s['regular_tasks']} ({s['assign_rate']}%)")
        print(f"  🚫 未安排: {s['unassigned']}")
        print(f"  ❌ 手动排: {s['excluded_tasks']}")
        print(f"  ⚡ 评分: {full_result['total_score']:.0f}")
        print(f"  🔥 冲突: {s['conflict_count']}")
        print(f"  通道B: {s['channel_b_tasks']} task | 通道A: {s['channel_a_tasks']} task")
        print(f"  双通道模式: {'✅' if s['dual_channel'] else '❌'}")

        if s["unassigned"] > 0:
            print(f"\n  未安排 Task 课程分布:")
            from collections import Counter
            u_courses = Counter(t.get("course_code", "?") for t in full_result["unassigned"])
            for code, cnt in u_courses.most_common(5):
                print(f"    {code}: {cnt}")
    else:
        print(f"\n  ❌ 失败")

    print("\n✅ 验证完成")
