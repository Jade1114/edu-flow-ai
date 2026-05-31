"""Placement Scorer — 对 (Task, Template, Room, Slot) 组合评分。

这是未来 LightGBM 评分模型的接口。
当前版本使用规则评分，数据结构与未来 ML 版本兼容。
"""

from __future__ import annotations


def score_placement(
    task: dict,
    template: dict,
    room: dict | None,
    slot: tuple[int, int, int],  # (week, day, period)
    current_timetable: dict,
    teacher_profiles: dict | None = None,
) -> dict:
    """对单个 (任务, 模板, 教室, 时段) 组合评分。

    Args:
        task: 教学任务
        template: 模板中的周次分配（含 weeks 列表）
        room: 教室信息
        slot: (week_number, day_of_week, period_index)
        current_timetable: 当前已排课表索引
        teacher_profiles: 教师画像数据（可选，未来扩展）

    Returns:
        {"score": 0.85, "breakdown": {...}}
    """
    score = 0.0
    breakdown = {}

    week, day, period = slot

    # 1. 模板匹配度 — 该 slot 是否在模板周次内
    if template and "weeks" in template:
        if week in template["weeks"]:
            weekly_idx = template["weeks"].index(week)
            lpwl = template.get("lessons_per_week_list", [])
            if weekly_idx < len(lpwl):
                # 模板周次内，得基础分
                score += 30.0
                breakdown["template_match"] = 30.0
        else:
            # 不在模板周次内，扣分
            score -= 20.0
            breakdown["template_mismatch"] = -20.0

    # 2. 早课/晚课惩罚
    if period == 1:
        early_penalty = task.get("early_period_penalty", 0)
        if isinstance(early_penalty, (int, float)) and early_penalty > 0:
            penalty = -10.0 * early_penalty
            score += penalty
            breakdown["early_period"] = penalty
    elif period >= 4:
        late_penalty = task.get("late_period_penalty", 0)
        if isinstance(late_penalty, (int, float)) and late_penalty > 0:
            penalty = -10.0 * late_penalty
            score += penalty
            breakdown["late_period"] = penalty

    # 3. 周末惩罚
    if day >= 6:
        weekend_penalty = task.get("weekend_penalty", 0)
        if isinstance(weekend_penalty, (int, float)) and weekend_penalty > 0:
            penalty = -15.0 * weekend_penalty
            score += penalty
            breakdown["weekend"] = penalty

    # 4. 教室容量匹配度
    if room:
        student_count = task.get("student_count", 30)
        capacity = room.get("capacity", 40)
        cap_ratio = student_count / max(1, capacity)
        if cap_ratio <= 1.0 and cap_ratio >= 0.5:
            cap_score = 15.0 * cap_ratio
            score += cap_score
            breakdown["capacity"] = cap_score
        elif cap_ratio < 0.5:
            cap_score = 5.0 * cap_ratio
            score += cap_score
            breakdown["capacity_loose"] = cap_score

    # 5. 同日课次惩罚（同一教师同日多节课）
    if room and week and day:
        teacher = task.get("teacher_id", 0)
        same_day_key = (teacher, week, day)
        same_day_count = current_timetable.get(same_day_key, 0)
        if same_day_count > 0:
            penalty = -5.0 * same_day_count
            score += penalty
            breakdown["same_day"] = penalty

    total_score = max(0.0, min(100.0, score + 50.0)) / 100.0

    return {
        "score": round(total_score, 4),
        "raw": round(score, 2),
        "breakdown": breakdown,
    }


def has_hard_conflict(
    task: dict,
    room_id: int | None,
    slot: tuple,
    state: dict,
) -> str | None:
    """硬约束检查。返回冲突原因或 None（无冲突）。"""
    week, day, period = slot
    teacher_id = task.get("teacher_id", 0)
    class_group_ids = task.get("class_group_ids", [])

    # 教师冲突：同一教师在相同 (week, day, period) 已有安排
    teacher_key = f"T:{teacher_id}:{week}:{day}:{period}"
    if teacher_key in state.get("teacher_slots", set()):
        return "教师时段冲突"

    # 班级冲突：班级在该时段已被占用
    for cgid in (class_group_ids if isinstance(class_group_ids, (list, tuple)) else [class_group_ids]):
        cg_key = f"CG:{cgid}:{week}:{day}:{period}"
        if cg_key in state.get("class_slots", set()):
            return f"班级冲突(cg={cgid})"

    # 教室冲突
    if room_id:
        room_key = f"R:{room_id}:{week}:{day}:{period}"
        if room_key in state.get("room_slots", set()):
            return "教室冲突"

    return None
