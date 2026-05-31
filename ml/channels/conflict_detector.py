"""Conflict Detector — 对完整课表做多维度冲突检测。

检测维度：
1. 教师冲突 — 同教师在相同时段教不同班
2. 班级冲突 — 同班级在相同时段上不同课
3. 教室冲突 — 同教室在相同时段被不同班使用

输出冲突图和连通分量，供局部修复引擎使用。
"""

from __future__ import annotations

import logging
from collections import defaultdict

_log = logging.getLogger("v2.conflict")


def detect_conflicts(assignments: list[dict]) -> dict:
    """对完整课表做多维度冲突检测。

    Args:
        assignments: [{week_number, day_of_week, period_index, teacher_id, ...}]

    Returns:
        {
            "total_assignments": N,
            "conflicts": {
                "teacher": [(slot_key, [{...}, {...}]), ...],
                "class": [(slot_key, [{...}, {...}]), ...],
                "room": [(slot_key, [{...}, {...}]), ...],
            },
            "conflict_count": N,
            "conflict_graph": {
                "nodes": [task_id, ...],
                "edges": [(task_id_A, task_id_B, "teacher"), ...],
                "clusters": [[task_id, ...], ...],  # 连通分量
            },
        }
    """
    # 1. 建索引
    teacher_slots: dict = defaultdict(list)
    class_slots: dict = defaultdict(list)
    room_slots: dict = defaultdict(list)

    for a in assignments:
        w = a.get("week_number")
        d = a.get("day_of_week")
        p = a.get("period_index")

        tid = a.get("task_id")
        tchr = a.get("teacher_id", 0)
        cg = a.get("class_group_ids", [])
        rm = a.get("room_id")

        slot = (w, d, p)
        teacher_slots[(tchr,) + slot].append(a)
        for c in (cg if isinstance(cg, (list, tuple)) else [cg]):
            class_slots[(c,) + slot].append(a)
        if rm:
            room_slots[(rm,) + slot].append(a)

    # 2. 找冲突：一个 slot 有多个安排即为冲突
    teacher_conflicts = []
    for key, items in teacher_slots.items():
        if len(items) > 1:
            teacher_conflicts.append((key, items))

    class_conflicts = []
    for key, items in class_slots.items():
        if len(items) > 1:
            class_conflicts.append((key, items))

    room_conflicts = []
    for key, items in room_slots.items():
        if len(items) > 1:
            room_conflicts.append((key, items))

    total_conflicts = len(teacher_conflicts) + len(class_conflicts) + len(room_conflicts)

    # 3. 构建冲突图
    # 节点 = assignment 的 task_id
    # 边 = 两个 assignment 在同一 slot 冲突
    edges: list[tuple] = []
    nodes: set = set()

    for _, items in teacher_conflicts:
        ids = [a.get("task_id") for a in items]
        for i in range(len(ids)):
            nodes.add(ids[i])
            for j in range(i + 1, len(ids)):
                edges.append((ids[i], ids[j], "teacher"))

    for _, items in class_conflicts:
        ids = [a.get("task_id") for a in items]
        for i in range(len(ids)):
            nodes.add(ids[i])
            for j in range(i + 1, len(ids)):
                edges.append((ids[i], ids[j], "class"))

    for _, items in room_conflicts:
        ids = [a.get("task_id") for a in items]
        for i in range(len(ids)):
            nodes.add(ids[i])
            for j in range(i + 1, len(ids)):
                edges.append((ids[i], ids[j], "room"))

    # 4. 找连通分量
    adj: dict = defaultdict(set)
    for n1, n2, _ in edges:
        adj[n1].add(n2)
        adj[n2].add(n1)

    visited: set = set()
    clusters: list[list] = []
    for node in nodes:
        if node in visited:
            continue
        # BFS 找连通分量
        queue = [node]
        component: set = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if component:
            clusters.append(list(component))

    _log.info("冲突检测: 总数=%d (教师=%d, 班级=%d, 教室=%d), "
              "冲突图: 节点=%d, 边=%d, 连通分量=%d",
              total_conflicts, len(teacher_conflicts), len(class_conflicts),
              len(room_conflicts), len(nodes), len(edges), len(clusters))

    return {
        "total_assignments": len(assignments),
        "conflicts": {
            "teacher": teacher_conflicts,
            "class": class_conflicts,
            "room": room_conflicts,
        },
        "conflict_count": total_conflicts,
        "conflict_graph": {
            "nodes": list(nodes),
            "edges": edges,
            "clusters": [sorted(c) for c in sorted(clusters, key=len, reverse=True)],
        },
    }


# ── 快速验证 ─────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 构造含冲突的测试数据
    assignments = [
        {"task_id": 1, "teacher_id": 10, "class_group_ids": [100], "room_id": 200,
         "week_number": 1, "day_of_week": 1, "period_index": 1},
        # 同一教师、同一班级、同一教室 → 故意冲突
        {"task_id": 2, "teacher_id": 10, "class_group_ids": [101], "room_id": 200,
         "week_number": 1, "day_of_week": 1, "period_index": 1},
        # 另一教师，无冲突
        {"task_id": 3, "teacher_id": 11, "class_group_ids": [100], "room_id": 201,
         "week_number": 1, "day_of_week": 1, "period_index": 2},
        # 班级冲突：任务3和任务4在同一班级id[100]、同一slot
        {"task_id": 4, "teacher_id": 12, "class_group_ids": [100], "room_id": 202,
         "week_number": 1, "day_of_week": 1, "period_index": 2},
    ]

    result = detect_conflicts(assignments)
    print(f"\n📊 冲突检测测试:")
    print(f"  总安排: {result['total_assignments']}")
    print(f"  冲突数: {result['conflict_count']}")
    for dtype, conflicts in result["conflicts"].items():
        for key, items in conflicts:
            ids = [a["task_id"] for a in items]
            print(f"  {dtype}: slot={key[1:]}  tasks={ids}")
    print(f"  连通分量: {result['conflict_graph']['clusters']}")
