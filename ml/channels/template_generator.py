"""Template Generator — 候选空间压缩第一步。

为每个教学任务计算 TopK 个合法排课模板。

模板 = 周次分配方案（每周上哪几天、哪几节）。

核心原则：
  按总课时/2 = 所需排课次数
  在可用周次内，枚举所有满足周课次约束的分配方案
  每种方案即是：[(week, day, period), ...] 的一个排列

输入：total_lessons（总课次）, available_weeks（可用周列表）
输出：TopK 个模板（按均匀度/紧凑度评分排序）
"""

from __future__ import annotations

import itertools
from collections import defaultdict


def generate_templates(
    total_lessons: int,
    available_weeks: list[int] | None = None,
    max_weekly_lessons: int = 6,
    top_k: int = 10,
) -> list[dict]:
    """为指定课次生成 TopK 节次分配方案。

    Args:
        total_lessons: 总课次数（总学时/2）
        available_weeks: 可选周次列表，默认1-18周
        max_weekly_lessons: 每周最多排几课次（默认6）
        top_k: 返回的最优方案数

    Returns:
        [
            {
                "rank": 1,
                "weeks": [1, 3, 5, ...],      # 上课周次
                "label": "每周4课时(2+2) 16周",
                "template_type": "even_2+2",
                "score": 0.95,                  # 0~1 评分
                "lessons_per_week": 2,          # 每周课次
                "total_weeks": 16,              # 总周数
            },
            ...
        ]
    """
    if available_weeks is None:
        available_weeks = list(range(1, 19))  # 1~18周

    total_lessons = max(1, total_lessons)
    candidates = _enumerate_templates(total_lessons, available_weeks, max_weekly_lessons)
    scored = _score_templates(candidates, total_lessons)
    top = sorted(scored, key=lambda t: -t["score"])[:top_k]

    for i, t in enumerate(top):
        t["rank"] = i + 1

    return top


# ── 内部实现 ────────────────────────────────────────

def _enumerate_templates(
    total_lessons: int,
    available_weeks: list[int],
    max_weekly_lessons: int,
) -> list[dict]:
    """枚举所有合法的周次分配方案。"""
    max_weeks = len(available_weeks)

    results = []

    # 策略1：每周均匀分布（尽可能每周排相同课次）
    for weekly in range(1, max_weekly_lessons + 1):
        total_weeks = (total_lessons + weekly - 1) // weekly  # ceil除法
        if total_weeks > max_weeks:
            continue
        weeks = available_weeks[:total_weeks]
        remaining = total_lessons - weekly * total_weeks
        # 如果剩余课次为负，说明最后一周不需要排满
        if remaining < 0:
            # 调整最后一周课次
            adjusted_weekly = weekly + remaining  # remaining为负
            if adjusted_weekly > 0:
                results.append({
                    "weeks": weeks,
                    "lessons_per_week_list": [weekly] * (total_weeks - 1) + [adjusted_weekly],
                    "template_type": f"even_{weekly}+{adjusted_weekly}",
                    "total_weeks": total_weeks,
                })
        else:
            results.append({
                "weeks": weeks,
                "lessons_per_week_list": [weekly] * total_weeks,
                "template_type": f"even_{weekly}",
                "total_weeks": total_weeks,
            })

    # 策略2：集中排课（尽可能压缩到更少的周次）
    for weekly in range(max_weekly_lessons, 0, -1):
        total_weeks = (total_lessons + weekly - 1) // weekly
        if total_weeks > max_weeks or total_weeks < 2:
            continue
        weeks = available_weeks[:total_weeks]
        remaining = total_lessons - weekly * total_weeks
        if remaining < 0:
            adjusted = weekly + remaining
            if adjusted > 0:
                results.append({
                    "weeks": weeks,
                    "lessons_per_week_list": [weekly] * (total_weeks - 1) + [adjusted],
                    "template_type": f"compact_{weekly}",
                    "total_weeks": total_weeks,
                })
        else:
            # 也加入紧凑方案
            pass  # already covered in strategy 1

    # 策略3：前重后轻（前几周多排，后期减少）
    if total_lessons > 4 and len(available_weeks) >= 8:
        # 前1/3周集中排课（模拟考试前课程密集）
        front_weeks = max(1, total_lessons // (max_weekly_lessons * 2))
        front_weeks = min(front_weeks, max_weeks // 3)
        if front_weeks > 0:
            front_lessons = min(total_lessons // 2, front_weeks * max_weekly_lessons)
            back_lessons = total_lessons - front_lessons
            back_weeks = (back_lessons + max_weekly_lessons - 1) // max_weekly_lessons
            total = front_weeks + back_weeks
            if total <= max_weeks:
                front_w = available_weeks[:front_weeks]
                back_w = available_weeks[front_weeks:front_weeks + back_weeks]
                lpwl = (
                    [max_weekly_lessons] * (front_lessons // max_weekly_lessons)
                    + [front_lessons % max_weekly_lessons] if front_lessons % max_weekly_lessons > 0 else []
                    + [max_weekly_lessons] * (back_lessons // max_weekly_lessons)
                )
                results.append({
                    "weeks": front_w + back_w,
                    "lessons_per_week_list": lpwl,
                    "template_type": "front_heavy",
                    "total_weeks": total,
                })

    # 策略4：隔周排课（双周排，周次均匀间隔）
    if total_lessons >= 4 and len(available_weeks) >= total_lessons * 2:
        for weekly in range(1, min(3, max_weekly_lessons) + 1):
            needed = (total_lessons + weekly - 1) // weekly
            if needed * 2 <= max_weeks:
                weeks = available_weeks[::2][:needed]
                if len(weeks) >= needed:
                    results.append({
                        "weeks": weeks,
                        "lessons_per_week_list": [weekly] * needed,
                        "template_type": "alternating",
                        "total_weeks": needed,
                    })

    # 策略5：交错式（如1+3+1+3...交替课次）
    if total_lessons >= 6:
        for pattern in [(2, 4), (1, 3), (3, 5)]:
            a, b = pattern
            cycle = a + b
            full_cycles = total_lessons // cycle
            remainder = total_lessons % cycle
            weeks_needed = full_cycles * 2 + (1 if remainder > 0 else 0)
            if weeks_needed <= max_weeks:
                lpwl = []
                for _ in range(full_cycles):
                    lpwl.extend([a, b])
                if remainder > 0:
                    lpwl.append(remainder)
                results.append({
                    "weeks": available_weeks[:weeks_needed],
                    "lessons_per_week_list": lpwl,
                    "template_type": f"alternating_{a}+{b}",
                    "total_weeks": weeks_needed,
                })

    return results


def _score_templates(candidates: list[dict], total_lessons: int) -> list[dict]:
    """为候选模板评分，0~1，越高越好。"""
    scored = []
    for t in candidates:
        weeks = t["weeks"]
        lpwl = t["lessons_per_week_list"]
        total_weeks = t["total_weeks"]

        # 1. 紧凑度评分（越紧凑越好）
        compactness = min(1.0, (total_lessons / max(1, total_weeks)) / 6.0)

        # 2. 均匀度评分（每周课次越均匀越好）
        if len(lpwl) > 1:
            variance = sum((x - sum(lpwl) / len(lpwl)) ** 2 for x in lpwl) / len(lpwl)
            uniformity = max(0, 1 - variance / 10.0)
        else:
            uniformity = 1.0

        # 3. 模板类型偏好
        type_bonus = {
            "even_2": 0.15,  # 每周2节最受欢迎
            "even_2+2": 0.12,
            "even_4": 0.10,
            "even_3": 0.08,
            "alternating_2+4": 0.05,
            "alternating_1+3": 0.03,
        }.get(t["template_type"], 0.0)

        # 4. 总可用周次利用率
        if weeks:
            week_span = weeks[-1] - weeks[0] + 1 if len(weeks) > 1 else 1
            span_penalty = min(0, -0.01 * (week_span - total_lessons * 2))
        else:
            span_penalty = 0

        t["score"] = round(min(1.0, compactness * 0.4 + uniformity * 0.3 + type_bonus + span_penalty), 4)
        t["lessons_per_week"] = lpwl[0] if lpwl else 2

        scored.append(t)

    return scored


# ── 快速验证 ─────────────────────────────────────────
if __name__ == "__main__":
    # 测试不同课次的模板生成
    for lessons in [4, 6, 8, 10, 12, 16]:
        templates = generate_templates(lessons, top_k=5)
        print(f"\n📚 total_lessons={lessons}:")
        for t in templates:
            lbl = f"{t['template_type']:20s} 周数={t['total_weeks']:2d} 每周={t['lessons_per_week']} 分={t['score']:.3f}"
            print(f"  [{t['rank']}] {lbl}")
