"""排课系统核心类型"""

from __future__ import annotations
from typing import Any, NamedTuple


# ── 模板 ──────────────────────────────────────────────────

class Template(NamedTuple):
    """一个模板 = 1 节课/周 × 若干生效周"""
    week_mask: int          # int32 bitmask, bit 0 = 周1
    weeks_list: list[int]   # for output only


class TemplateSet(NamedTuple):
    """一个模板方案 = 若干模板 + 预计算评分"""
    templates: list[Template]
    penalty: float           # 段数/均匀性/连续性 加权


# ── 教学任务 + 生成配置（运行时合并） ───────────────────

class AllocationTask(NamedTuple):
    task_id: int
    teacher_id: int
    class_group_id: int          # 兼容旧调用：主班级/第一个班级
    student_count: int
    total_lessons: int           # 总课时/2 = 需要排的次课数
    available_week_mask: int     # bitmask
    candidate_slot_ids: list[int]   # 0~24
    candidate_room_ids: list[int]   # 按容量/类型过滤后的教室 id
    template_sets: list[TemplateSet]
    class_group_ids: tuple[int, ...] = ()  # 合班课需要检查所有班级冲突
    teacher_profile: dict[str, Any] | None = None


# ── 染色体 ────────────────────────────────────────────────

class TemplateAssignment(NamedTuple):
    template_id: int     # 在 TemplateSet 内的索引
    slot_id: int         # 0~24, 对应 (day, period) pair
    classroom_id: int


class TaskGene(NamedTuple):
    task_id: int
    template_set_id: int
    assignments: list[TemplateAssignment]


# ── Slot 工具 ─────────────────────────────────────────────


def slot_to_day_period(slot_id: int) -> tuple[int, int]:
    """slot 0~24 → (day 1~5, period 1~5)"""
    return (slot_id // 5 + 1, slot_id % 5 + 1)


def day_period_to_slot(day: int, period: int) -> int:
    """(day 1~5, period 1~5) → slot 0~24"""
    return (day - 1) * 5 + (period - 1)


def real_time_slot_id(week: int, day: int, period: int) -> int:
    """Java 端 time_slot_id：(week-1)*35 + (day-1)*5 + period"""
    return (week - 1) * 35 + (day - 1) * 5 + period


# ── Bitmask 工具 ──────────────────────────────────────────


def weeks_to_mask(weeks: list[int]) -> int:
    mask = 0
    for w in weeks:
        mask |= 1 << (w - 1)
    return mask


def mask_to_weeks(mask: int, max_weeks: int = 18) -> list[int]:
    return [i + 1 for i in range(max_weeks) if mask & (1 << i)]


def weeks_overlap(a: int, b: int) -> bool:
    return (a & b) != 0


def mask_count(mask: int) -> int:
    return bin(mask).count("1")
