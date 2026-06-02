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

    def __init__(self, locked_slots: dict | None = None):
        self.assignments: list[dict] = []  # 已放置的任务
        self.teacher_slots: set[str] = set()
        self.class_slots: set[str] = set()
        self.room_slots: set[str] = set()
        self.room_usage: dict[int, int] = defaultdict(int)
        self.total_score: float = 0.0

        # 双通道支持：通道A需避开通道B已锁定资源
        if locked_slots:
            self.teacher_slots.update(locked_slots.get("teacher_slots", set()))
            self.class_slots.update(locked_slots.get("class_slots", set()))
            self.room_slots.update(locked_slots.get("room_slots", set()))

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
            slot: tuple, score: float, slot_index: dict | None = None):
        """放置一个任务到课表。"""
        week, day, period = slot
        teacher_id = task.get("teacher_id", 0)
        room_id = (room.get("room_id") or room.get("id")) if room else None

        # 用 slot_index 查实际 time_slot_id（DB 自增 ID，非公式计算）
        if slot_index:
            time_slot_id_val = slot_index.get((week, day, period))
        if not slot_index or time_slot_id_val is None:
            # 兜底：退回到公式计算（仅在 slot_index 不可用时）
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
    locked_slots: dict | None = None,
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

    # 3. Beam Search (支持双通道：锁定资源在前)
    beam: list[BeamState] = [BeamState(locked_slots=locked_slots)]
    unassigned = []
    stats = {"total": len(sorted_tasks), "assigned": 0, "failed": 0}

    # 预先为每个 task 生成最佳模板（仅用来获取评分参考，周次覆盖被覆盖）
    task_templates: dict[int, dict | None] = {}
    for task in sorted_tasks:
        total_lessons = task.get("total_lessons", 4)
        tmpls = generate_templates(total_lessons, top_k=1)
        task_templates[task.get("id", 0)] = tmpls[0] if tmpls else None

    for task in sorted_tasks:
        total_lessons = task.get("total_lessons", 4)
        tmpl = task_templates.get(task.get("id", 0))
        if tmpl is None:
            _log.warning(f"无法安排: {task.get('teacher_name','?')} — 无可用模板")
            unassigned.append(task)
            stats["failed"] += 1
            continue

        # 周次分配：显式打包，保证每个 session 有周次，覆盖学期全程
        total_sessions_needed: int = total_lessons
        semester_weeks_count: int = len(week_list)
        max_per_week = tmpl.get("lessons_per_week", 2)

        # 计算各周应放 session 数：先给每周 1 个，余数从学期末尾开始加
        weekly_counts: list[int] = [1] * semester_weeks_count
        total_base = semester_weeks_count
        extra = total_sessions_needed - total_base
        if extra > 0:
            # 从末尾开始每追加一个 session 到已有 max_per_week 的周
            for w_idx in range(semester_weeks_count - 1, -1, -1):
                if extra <= 0:
                    break
                addable = max_per_week - weekly_counts[w_idx]
                if addable > 0:
                    delta = min(extra, addable)
                    weekly_counts[w_idx] += delta
                    extra -= delta
        elif extra < 0:
            # session 少于学期周数：从学期末尾去掉多余的
            for w_idx in range(semester_weeks_count - 1, -1, -1):
                if extra >= 0:
                    break
                weekly_counts[w_idx] = 0
                extra += 1

        # 展开为候选列表
        candidate_weeks: list[int] = []
        for w_idx, cnt in enumerate(weekly_counts):
            for _ in range(cnt):
                candidate_weeks.append(week_list[w_idx])

        _log.debug("  %s: %d sessions → %d weeks, weekly_counts=%s",
                   task.get('teacher_name', '?'), total_sessions_needed,
                   sum(1 for c in weekly_counts if c > 0), weekly_counts[:10])

        candidate_states: list[tuple[float, BeamState]] = []

        # 为每个 beam state 生成候选：柔性周次分配
        for state in beam:
            hard_state = {
                "teacher_slots": state.teacher_slots,
                "class_slots": state.class_slots,
                "room_slots": state.room_slots,
            }

            # 生成推荐教室（复用一次）
            rooms = rank_rooms(task, classrooms, dict(state.room_usage), top_k=3,
                                diversity_seed=task.get("id", 0))
            if not rooms:
                continue

            all_placements: list[tuple] = []  # [(week, slot, room, score), ...]
            placed_count = 0

            # 按 candidate_weeks 顺序逐周放置，每轮放 1 个 session
            # candidate_weeks 已包含每个 session 的独立周次分配
            for w in candidate_weeks:
                if placed_count >= total_sessions_needed:
                    break

                best_for_slot = None
                best_score = -99999

                for d, p in day_period_list:
                    slot = (w, d, p)
                    conflict = has_hard_conflict(task, None, slot, hard_state)
                    if conflict:
                        continue

                    for room in rooms:
                        conflict = has_hard_conflict(task, room["room_id"], slot, hard_state)
                        if conflict:
                            continue

                        result = score_placement(task, tmpl, room, slot, hard_state)
                        score = result["score"]
                        if score > best_score:
                            best_score = score
                            best_for_slot = (w, slot, room)

                if best_for_slot:
                    all_placements.append((*best_for_slot, best_score))
                    placed_count += 1
                    # 标记这个 slot 已占用，防止同周其他 session 冲突
                    _, slot, room = best_for_slot
                    w_used, d_used, p_used = slot
                    key = f"T:{task.get('teacher_id',0)}:{w_used}:{d_used}:{p_used}"
                    if key not in hard_state["teacher_slots"]:
                        hard_state["teacher_slots"].add(key)
                    for cg in (task.get("class_group_ids", []) if isinstance(task.get("class_group_ids", []), list) else []):
                        hard_state["class_slots"].add(f"CG:{cg}:{w_used}:{d_used}:{p_used}")
                    if room:
                        hard_state["room_slots"].add(f"R:{room['room_id']}:{w_used}:{d_used}:{p_used}")
                # 当前周没空位 → 跳过这个 session（后续 candidate_weeks 可能有同周的其他条目）

            total_needed = total_sessions_needed
            avg_score = sum(p[3] for p in all_placements) / max(len(all_placements), 1)

            # 每个 beam state 扩展为一个新 state
            new_state = state.clone()
            for w, slot, room, score in all_placements:
                new_state.add(task, tmpl, room, slot, score, slot_index=slot_index)

            # 用平均分 + 完成率加权作为这个扩展的总分
            completion_ratio = len(all_placements) / max(total_needed, 1)
            state_total = new_state.total_score - state.total_score  # 增量
            composite_score = state_total * completion_ratio

            # 把 new_state 加入候选列表供 beam 选取
            candidate_states.append((composite_score, new_state))

        # 已遍历完全部 beam state，从候选列表中取 TopB

        if not candidate_states:
            _log.warning(f"无法安排: {task.get('teacher_name','?')} — 无法在任何 beam state 中放置")
            unassigned.append(task)
            stats["failed"] += 1
            continue

        # 按 composite_score 排序取 TopB
        candidate_states.sort(key=lambda x: -x[0])
        beam = [cs[1] for cs in candidate_states[:beam_width]]
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
