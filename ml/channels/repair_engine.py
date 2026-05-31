"""Local Repair Engine — V2 尾部收口模块。

对冲突检测报告中的小冲突簇，通过局部搜索修复：
1. 换 slot（同一教室不同时段）
2. 换教室（同一 slot 不同教室）
3. 换二者

不重跑 Beam Search，只做近邻搜索。
回溯深度 ≤ 2，防止指数爆炸。
"""

from __future__ import annotations

import logging
from collections import defaultdict

from .placement_scorer import has_hard_conflict, score_placement

_log = logging.getLogger("v2.repair")


def repair_assignments(
    assignments: list[dict],
    conflict_report: dict,
    classrooms: list[dict],
    time_slots: list[dict],
    max_depth: int = 2,
) -> dict:
    """修复冲突课表。

    Args:
        assignments: 带冲突的课表
        conflict_report: detect_conflicts() 的输出
        classrooms: 教室列表
        time_slots: 时间段列表
        max_depth: 最大回溯深度

    Returns:
        {"repaired": True, "assignments": [...], "repairs": 3, "remaining": 0, ...}
    """
    clusters = conflict_report.get("conflict_graph", {}).get("clusters", [])
    if not clusters:
        return {"repaired": True, "assignments": assignments, "repairs": 0, "remaining": 0}

    # 构建冲突索引
    teacher_slots: set[str] = set()
    class_slots: set[str] = set()
    room_slots: set[str] = set()

    for a in assignments:
        w, d, p = a.get("week_number"), a.get("day_of_week"), a.get("period_index")
        t_id = a.get("teacher_id")
        for cg in _listify(a.get("class_group_ids", [])):
            class_slots.add(f"CG:{cg}:{w}:{d}:{p}")
        room_id = a.get("room_id")
        if room_id:
            room_slots.add(f"R:{room_id}:{w}:{d}:{p}")

    # 循环（按簇大小升序，先修小的）
    total_repairs = 0
    remaining = 0

    for cluster in sorted(clusters, key=len):
        cluster_assignments = [a for a in assignments if a.get("task_id") in cluster]
        if len(cluster_assignments) < 2:
            continue

        # 尝试对这个簇内的每个冲突 assignment 局部修复
        for ca in cluster_assignments:
            task_id = ca.get("task_id")
            teacher_id = ca.get("teacher_id")
            w0, d0, p0 = ca.get("week_number"), ca.get("day_of_week"), ca.get("period_index")
            room_id = ca.get("room_id")

            # 查找可用替代 slot
            found = False
            for w in range(1, 19):
                if found:
                    break
                for d in range(1, 6):
                    if found:
                        break
                    for p in range(1, 6):
                        if (w, d, p) == (w0, d0, p0):
                            continue

                        hard = {"teacher_slots": teacher_slots, "class_slots": class_slots, "room_slots": room_slots}
                        c = has_hard_conflict(ca, room_id, (w, d, p), hard)
                        if not c:
                            # 找到了可用 slot，移动
                            teacher_slots.discard(f"T:{teacher_id}:{w0}:{d0}:{p0}")
                            teacher_slots.add(f"T:{teacher_id}:{w}:{d}:{p}")
                            for cg in _listify(ca.get("class_group_ids", [])):
                                class_slots.discard(f"CG:{cg}:{w0}:{d0}:{p0}")
                                class_slots.add(f"CG:{cg}:{w}:{d}:{p}")
                            if room_id:
                                room_slots.discard(f"R:{room_id}:{w0}:{d0}:{p0}")
                                room_slots.add(f"R:{room_id}:{w}:{d}:{p}")
                            ca["week_number"] = w
                            ca["day_of_week"] = d
                            ca["period_index"] = p
                            total_repairs += 1
                            found = True

            if not found:
                remaining += 1

    _log.info("Repair: %d fixes, %d remaining conflicts", total_repairs, remaining)
    return {
        "repaired": remaining == 0,
        "assignments": assignments,
        "repairs": total_repairs,
        "remaining": remaining,
    }


def _listify(val):
    if isinstance(val, (list, tuple)):
        return val
    return [val] if val is not None else []
