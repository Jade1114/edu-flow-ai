"""Beam Search 构造器 — V2 核心排课引擎。

流程：
1. 教学任务按优先级排序（高交叉教师 → 低交叉教师）
2. 维护 TopB 个局部课表
3. 每个任务：
   a. 对每个局部课表，生成 (模板, 教室, slot) 候选
   b. 硬约束过滤
   c. Placement Scorer 评分
   d. 选 TopB 个最优扩展
4. 返回最优完整课表

LightGBM 可在此处注入 Placement Scorer。
"""

from __future__ import annotations

import logging
from collections import defaultdict

_log = logging.getLogger("v2.beam")

try:
    from ml.channels.template_generator import generate_templates
    from ml.channels.room_ranker import rank_rooms
    from ml.channels.placement_scorer import score_placement, has_hard_conflict
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.channels.template_generator import generate_templates
    from ml.channels.room_ranker import rank_rooms
    from ml.channels.placement_scorer import score_placement, has_hard_conflict


class BeamState:
    """Beam search 的局部课表状态。"""

    def __init__(self):
        self.assignments: list[dict] = []  # 已放置的任务
        self.teacher_slots: set[str] = set()
        self.class_slots: set[str] = set()
        self.room_slots: set[str] = set()
        self.room_usage: dict[int, int] = defaultdict(int)
        self.total_score: float = 0.0

    def clone(self) -> BeamState:
        s = BeamState()
        s.assignments = list(self.assignments)
        s.teacher_slots = set(self.teacher_slots)
        s.class_slots = set(self.class_slots)
        s.room_slots = set(self.room_slots)
        s.room_usage = defaultdict(int, self.room_usage)
        s.total_score = self.total_score
        return s

    def add(self, task: dict, template: dict, room: dict | None,
            slot: tuple, score: float):
        """放置一个任务到课表。"""
        week, day, period = slot
        teacher_id = task.get("teacher_id", 0)
        room_id = (room.get("room_id") or room.get("id")) if room else None

        # 构造 Java 持久层需要的 time_slot_id（匹配 DB 自增规则）
        time_slot_id_val = 1001 + (week - 1) * 25 + (day - 1) * 5 + (period - 1)

        self.assignments.append({
            "task_id": task.get("id"),
            "teaching_task_id": task.get("id"),
            "teacher_id": teacher_id,
            "teacher_name": task.get("teacher_name", ""),
            "class_group_ids": task.get("class_group_ids", []),
            "total_lessons": task.get("total_lessons", 0),
            "week_number": week,
            "day_of_week": day,
            "period_index": period,
            "time_slot_id": time_slot_id_val,
            "room_id": room_id,
            "classroom_id": room_id,
            "room_name": room.get("name", "") if room else "",
            "template_type": template.get("template_type", ""),
            "placement_score": score,
        })

        # 更新冲突索引
        self.teacher_slots.add(f"T:{teacher_id}:{week}:{day}:{period}")
        cg_ids = task.get("class_group_ids", [])
        if isinstance(cg_ids, (list, tuple)):
            for cg in cg_ids:
                self.class_slots.add(f"CG:{cg}:{week}:{day}:{period}")
        else:
            self.class_slots.add(f"CG:{cg_ids}:{week}:{day}:{period}")
        if room_id:
            self.room_slots.add(f"R:{room_id}:{week}:{day}:{period}")
            self.room_usage[room_id] += 1

        self.total_score += score


def construct_timetable(
    tasks: list[dict],
    classrooms: list[dict],
    time_slots: list[dict],
    beam_width: int = 3,
    teacher_priority: list[str] | None = None,
    max_iterations: int | None = None,
) -> dict:
    """Beam Search 构造全校课表。

    Args:
        tasks: 教学任务列表
        classrooms: 教室列表
        time_slots: 时间段列表
        beam_width: Beam宽度（默认3）
        teacher_priority: 高优先级教师列表（这些教师的任务先排）
        max_iterations: 最大迭代次数（限制总运行时间）

    Returns:
        {"success": True,
         "assignments": [...],
         "total_score": 123.4,
         "unassigned": [...],
         "stats": {...}}
    """
    # 1. 任务排序
    high_priority_teachers = set(teacher_priority or [])
    sorted_tasks = _sort_tasks(tasks, high_priority_teachers)

    if max_iterations:
        sorted_tasks = sorted_tasks[:max_iterations]

    # 2. 按 (day, period) 构建 slot 查询索引
    slot_index = {}
    day_period_set = set()
    for s in time_slots:
        w = int(s.get("week_number", 0))
        d = int(s.get("day_of_week", 0))
        p = int(s.get("period_index", 0))
        slot_index[(w, d, p)] = s.get("id", 0)
        day_period_set.add((d, p))

    # 所有可用的 (day, period) 组合
    week_list = sorted(set(int(s["week_number"]) for s in time_slots))
    day_period_list = sorted(day_period_set)

    # 3. Beam Search
    beam: list[BeamState] = [BeamState()]
    unassigned = []
    stats = {"total": len(sorted_tasks), "assigned": 0, "failed": 0}

    for task in sorted_tasks:
        candidates = []
        iter_counts: dict[str, int] = {"state_skip": 0, "template": 0, "slot": 0, "hard_tc": 0, "room_loop": 0, "hard_rc": 0, "placed": 0}

        # 为每个 beam 中的局部课表生成候选
        for state in beam:
            # 过滤硬约束索引
            hard_state = {
                "teacher_slots": state.teacher_slots,
                "class_slots": state.class_slots,
                "room_slots": state.room_slots,
            }

            # 检查是否已排（用 task_id + total_lessons 联合校验，同教师不同课时不会误判）
            tid = task.get("id", 0)
            tlessons = task.get("total_lessons", 0)
            if any(a.get("task_id") == tid and a.get("total_lessons") == tlessons for a in state.assignments):
                iter_counts["state_skip"] += 1
                continue

            # 生成模板
            total_lessons = task.get("total_lessons", 4)
            templates = generate_templates(total_lessons, top_k=3)

            # 生成推荐教室
            rooms = rank_rooms(task, classrooms, dict(state.room_usage), top_k=3,
                                diversity_seed=task.get("id", 0))

            # 生成候选 (week, day, period, room)
            for tmpl in templates:
                iter_counts["template"] += 1
                for w in tmpl["weeks"]:
                    for d, p in day_period_list:
                        iter_counts["slot"] += 1
                        slot = (w, d, p)

                        # 硬约束过滤（教师+班级）
                        conflict = has_hard_conflict(task, None, slot, hard_state)
                        if conflict:
                            iter_counts["hard_tc"] += 1
                            continue

                        # 对每个推荐教室评分
                        for room in rooms:
                            iter_counts["room_loop"] += 1
                            conflict = has_hard_conflict(task, room["room_id"], slot, hard_state)
                            if conflict:
                                iter_counts["hard_rc"] += 1
                                continue

                            # Placement Scorer
                            result = score_placement(
                                task, tmpl, room, slot, hard_state
                            )

                            candidates.append({
                                "state": state,
                                "task": task,
                                "template": tmpl,
                                "room": room,
                                "slot": slot,
                                "score": result["score"],
                                "breakdown": result.get("breakdown", {}),
                            })
                            iter_counts["placed"] += 1

        if not candidates:
            teacher_name = task.get("teacher_name", "?")
            _log.warning(f"无法安排: {teacher_name} — 迭代追踪: {iter_counts}")
            unassigned.append(task)
            stats["failed"] += 1
            continue

        # 按评分降序取 TopB 个扩展
        # 每个 beam state 独立贡献候选，不跨 beam 去重
        candidates.sort(key=lambda c: -c["score"])
        best_states: list[BeamState] = []
        seen_beam_ids: set[int] = set()

        for cand in candidates:
            bid = id(cand["state"])
            # 已经从这个 beam state 选了一个扩展，跳过后续同 beam 的候选
            if bid in seen_beam_ids:
                continue

            new_state = cand["state"].clone()
            new_state.add(
                cand["task"], cand["template"],
                cand["room"], cand["slot"], cand["score"],
            )
            best_states.append(new_state)
            seen_beam_ids.add(bid)

            if len(best_states) >= beam_width:
                break

        beam = best_states[:beam_width]
        stats["assigned"] += 1

    # 4. 返回最优完整课表
    if not beam:
        return {"success": False, "error": "没有可行解", "unassigned": unassigned, "stats": stats}

    best = max(beam, key=lambda s: s.total_score)
    return {
        "success": True,
        "assignments": best.assignments,
        "total_score": best.total_score,
        "unassigned": unassigned,
        "stats": stats,
        "beam_count": len(beam),
    }


def _sort_tasks(tasks: list[dict], high_priority_teachers: set[str]) -> list[dict]:
    """按优先级排序教学任务。高交叉教师、需特殊教室的任务优先。"""
    def priority(task: dict) -> int:
        p = 0
        # 高交叉教师优先
        if task.get("teacher_name") in high_priority_teachers:
            p -= 100
        # 需要特定教室类型优先
        rtype = task.get("required_room_type", "")
        if rtype and rtype not in ("", "普通教室"):
            p -= 50
        # 学生多的优先
        p -= min(0, task.get("student_count", 0) // 10)
        # 课时多的优先
        p -= min(0, task.get("total_lessons", 0))
        return p

    return sorted(tasks, key=priority)


# ── 快速验证 ─────────────────────────────────────────
if __name__ == "__main__":
    import json
    from pathlib import Path

    # 加载小样本数据
    DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
    tasks_raw = [json.loads(l) for l in (DATA / "teaching_tasks.jsonl").read_text().splitlines() if l.strip()]
    classrooms_raw = [json.loads(l) for l in (DATA / "classrooms.jsonl").read_text().splitlines() if l.strip()]

    # 取一个班（10 个任务）验证
    cg = "2023级软件工程2班"
    sample_tasks = [t for t in tasks_raw if t["class_group"] == cg][:10]

    alloc_tasks = []
    for tt in sample_tasks:
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

    classrooms = []
    for cr in classrooms_raw[:50]:
        classrooms.append({
            "id": int(hash(cr["name"])) % 10000 + 1,
            "name": cr["name"],
            "capacity": 80,
            "classroom_type": cr.get("classroom_type", ""),
        })

    time_slots = [
        {"id": w * 100 + d * 10 + p, "week_number": w, "day_of_week": d, "period_index": p}
        for w in range(1, 19)
        for d in range(1, 6)
        for p in range(1, 6)
    ]

    print(f"📊 Beam Search 验证: {len(alloc_tasks)} 个任务")
    result = construct_timetable(alloc_tasks, classrooms, time_slots, beam_width=2)

    if result["success"]:
        print(f"  ✅ 成功: {len(result['assignments'])} 个安排")
        print(f"  总评分: {result['total_score']:.2f}")
        print(f"  未安排: {len(result['unassigned'])} 个")
        print(f"\n  课表示例:")
        for a in result["assignments"][:5]:
            print(f"    周{a['week_number']} 周{a['day_of_week']} 第{a['period_index']}节 "
                  f"{a['teacher_name']} → {a.get('room_name', '?')}")
    else:
        print(f"  ❌ 失败: {result.get('error')}")
        print(f"  未安排: {len(result['unassigned'])} 个")
