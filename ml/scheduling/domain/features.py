"""Feature engineering and scoring helpers for training sample generation.

This module bridges GA's rule-based scoring with LightGBM training:
  - GA 的 _slot_room_penalty() 做排课时的实时惩罚计算
  - score_sample() 在这里做训练样本的标签计算（规则伪标签）
  - 其余函数负责从 DB 数据构建特征
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any


# ── 基础工具 ──────────────────────────────────────────────


def parse_id_tuple(value: Any) -> tuple[int, ...]:
    """解析各种格式的 ID 列表为 tuple[int]"""
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = str(value).strip().strip("[]").replace(" ", "").split(",")

    ids: list[int] = []
    for part in raw_parts:
        if part in ("", None):
            continue
        try:
            parsed = int(part)
        except (TypeError, ValueError):
            continue
        if parsed and parsed not in ids:
            ids.append(parsed)
    return tuple(ids)


def is_room_type_match(required: str, actual: str) -> bool:
    """检查教室类型是否匹配。空 required 视为不限制。"""
    if not required or not required.strip():
        return True
    return required.strip().lower() == actual.strip().lower()


def effective_required_room_type(task: dict[str, Any]) -> str:
    """从任务中提取有效教室类型要求。"""
    return str(task.get("required_room_type") or "").strip()


def periods_needed(task: dict[str, Any]) -> int:
    """计算需要的排课次数（总课时 / 2 = 排课次数）。"""
    return max(1, int(task.get("total_hours") or 0) // 2)


# ── 伪排课与占用索引 ──────────────────────────────────────


def build_pseudo_assignments(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """构建伪排课方案，用于计算各维度的占用情况。

    将每个教学任务分配到它可能的第一周 + 第一个可用时间段 + 第一个可用教室，
    构造一个"基线状态"以便计算 teacher_day_load / teacher_week_load 等特征。
    """
    if not time_slots:
        return []

    # 按 week_number 排序，取第一周作为基线
    sorted_slots = sorted(time_slots, key=lambda s: int(s.get("week_number") or 0))
    first_week = int(sorted_slots[0].get("week_number") or 1)

    # 取该周的第一个时间段作为伪指派
    first_week_slots = [s for s in sorted_slots if int(s.get("week_number") or 0) == first_week]
    if not first_week_slots:
        first_week_slots = sorted_slots[:1]

    first_slot = first_week_slots[0]
    slot_id = int(first_slot.get("id") or 0)
    week_number = int(first_slot.get("week_number") or 1)
    day_of_week = int(first_slot.get("day_of_week") or 1)
    period_index = int(first_slot.get("period_index") or 1)

    first_room = classrooms[0] if classrooms else {}
    room_id = int(first_room.get("id") or 0)

    assignments: list[dict[str, Any]] = []
    for task in tasks:
        task_id = int(task.get("teaching_task_id") or 0)
        teacher_id = int(task.get("teacher_id") or 0)
        class_group_ids = parse_id_tuple(task.get("class_group_ids"))
        cg_id = class_group_ids[0] if class_group_ids else int(task.get("class_group_id") or 1)

        assignments.append({
            "teaching_task_id": task_id,
            "teacher_id": teacher_id,
            "class_group_ids": class_group_ids or (cg_id,),
            "classroom_id": room_id,
            "time_slot_id": slot_id,
            "week_number": week_number,
            "day_of_week": day_of_week,
            "period_index": period_index,
        })

    return assignments


def build_occupied_indexes(assignments: list[dict[str, Any]]) -> dict[str, dict]:
    """从伪排课方案构建多维度占用索引。

    返回字典包含：
      - teacher_slot[(teacher_id, slot_id)] → set[task_id]
      - class_slot[(class_group_id, slot_id)] → set[task_id]
      - room_slot[(room_id, slot_id)] → set[task_id]
      - teacher_day_load[(teacher_id, week, day)] → int
      - teacher_week_load[(teacher_id, week)] → int
      - class_day_load[(class_group_id, week, day)] → int
      - class_week_load[(class_group_id, week)] → int
      - scheme_day_load[(week, day)] → int
      - task_day_load[(task_id, week, day)] → int
      - room_day_load[(room_id, week, day)] → int
      - room_week_load[(room_id, week)] → int
    """
    indexes: dict[str, dict] = {
        "teacher_slot": defaultdict(set),
        "class_slot": defaultdict(set),
        "room_slot": defaultdict(set),
        "teacher_day_load": defaultdict(int),
        "teacher_week_load": defaultdict(int),
        "class_day_load": defaultdict(int),
        "class_week_load": defaultdict(int),
        "scheme_day_load": defaultdict(int),
        "task_day_load": defaultdict(int),
        "room_day_load": defaultdict(int),
        "room_week_load": defaultdict(int),
    }

    for a in assignments:
        task_id = int(a["teaching_task_id"])
        teacher_id = int(a["teacher_id"])
        class_group_ids = a.get("class_group_ids") or ()
        room_id = int(a.get("classroom_id") or 0)
        slot_id = int(a.get("time_slot_id") or 0)
        wn = int(a.get("week_number") or 1)
        day = int(a.get("day_of_week") or 1)
        period = int(a.get("period_index") or 1)

        key_slot = slot_id
        key_day = day
        key_week_day = (wn, day)

        indexes["teacher_slot"][(teacher_id, key_slot)].add(task_id)
        indexes["teacher_day_load"][(teacher_id, wn, day)] += 1
        indexes["teacher_week_load"][(teacher_id, wn)] += 1

        for cg_id in class_group_ids:
            cg = int(cg_id)
            indexes["class_slot"][(cg, key_slot)].add(task_id)
            indexes["class_day_load"][(cg, wn, day)] += 1
            indexes["class_week_load"][(cg, wn)] += 1

        indexes["room_slot"][(room_id, key_slot)].add(task_id)
        indexes["room_day_load"][(room_id, wn, day)] += 1
        indexes["room_week_load"][(room_id, wn)] += 1

        indexes["scheme_day_load"][key_week_day] += 1
        indexes["task_day_load"][(task_id, wn, day)] += 1

    # 将 defaultdict 转为普通 dict 以便 JSON 序列化
    return {k: dict(v) for k, v in indexes.items()}


# ── 拒绝原因 ──────────────────────────────────────────────


def reject_reason(
    teacher_conflict: bool = False,
    class_conflict: bool = False,
    room_conflict: bool = False,
    capacity_enough: bool = True,
    type_match: bool = True,
) -> str:
    """生成可读的拒绝原因（用于训练样本的 debug 字段）。"""
    reasons: list[str] = []
    if teacher_conflict:
        reasons.append("教师冲突")
    if class_conflict:
        reasons.append("班级冲突")
    if room_conflict:
        reasons.append("教室冲突")
    if not capacity_enough:
        reasons.append("教室容量不足")
    if not type_match:
        reasons.append("教室类型不匹配")
    return "；".join(reasons) if reasons else ""


# ── 规则打分引擎（核心） ──────────────────────────────────


def score_sample(
    has_hard_conflict: bool,
    is_type_match: bool,
    capacity_ratio: float,
    is_early_period: bool,
    is_late_period: bool,
    teacher_day_load: int = 0,
    class_day_load: int = 0,
    teacher_week_load: int = 0,
    teacher_max_weekly_hours: int | None = None,
) -> float:
    """基于规则为 (task × slot × classroom) 组合打分。

    返回 [0.0, 1.0] 的分数，越高代表该指派质量越好。
    用作 LightGBM 冷启动的伪标签，等有真实反馈后再替换。

    评分逻辑：
      1. 硬冲突 → 直接 0.0
      2. 无冲突 → 从 1.0 开始扣分：
         - 教室类型不匹配 → -0.20
         - 容量偏离过大（< 60% 或 > 100%）→ -0.15
         - 早八 → -0.10
         - 晚课 → -0.05
         - 教师当天已有课时 → -0.05 × 每课时
         - 教师周课时超标 → -0.10
         - 班级当天已有课时 → -0.03 × 每课时
    """
    if has_hard_conflict:
        return 0.0

    score = 1.0

    # 教室类型不匹配
    if not is_type_match:
        score -= 0.20

    # 容量偏离惩罚
    if capacity_ratio < 0.6:
        score -= 0.15  # 教室太大，浪费
    elif capacity_ratio > 1.0:
        score -= 0.15  # 教室不够坐（应被硬冲突捕获，但以防万一）
    elif capacity_ratio > 0.85:
        pass  # 高利用率，完美
    elif capacity_ratio < 0.75:
        score -= 0.08  # 稍大

    # 时间段偏好
    if is_early_period:
        score -= 0.10  # 早八
    if is_late_period:
        score -= 0.05  # 晚课

    # 教师日负载
    if teacher_day_load > 0:
        score -= 0.05 * teacher_day_load

    # 教师周课时超标
    if teacher_max_weekly_hours and teacher_week_load > teacher_max_weekly_hours:
        score -= 0.10 * (teacher_week_load - teacher_max_weekly_hours)

    # 班级日负载
    if class_day_load > 0:
        score -= 0.03 * class_day_load

    return max(0.0, min(1.0, score))
