"""多策略候选方案生成 + 综合评价。

生成 N 个不同策略的候选课表，用多个维度评分后选最优。
"""

from __future__ import annotations

import logging

from .integration import generate_v2

_log = logging.getLogger("v2.strategy")


# 5 种策略配置
STRATEGIES = [
    {"name": "教师优先", "beam_width": 3, "high_cross_threshold": 8, "desc": "高交叉教师门槛降低，更多教师优先"},
    {"name": "均衡优先", "beam_width": 3, "high_cross_threshold": 12, "desc": "默认配置"},
    {"name": "探索优先", "beam_width": 5, "high_cross_threshold": 12, "desc": "宽波束，更多探索"},
    {"name": "教室优先", "beam_width": 3, "high_cross_threshold": 16, "desc": "更多教师并行，减少教室冲突"},
    {"name": "紧凑优先", "beam_width": 4, "high_cross_threshold": 10, "desc": "折中配置"},
]


def generate_multi_strategy(
    tasks: list[dict],
    classrooms: list[dict],
    time_slots: list[dict],
) -> list[dict]:
    """用多种策略生成候选方案。

    Returns:
        [{ "strategy": str, "assignments": [...], "scores": {...} }, ...]
    """
    candidates = []

    for s in STRATEGIES:
        _log.info("策略: %s — %s", s["name"], s["desc"])
        try:
            result = generate_v2(
                tasks, classrooms, time_slots,
                beam_width=s["beam_width"],
                high_cross_threshold=s["high_cross_threshold"],
            )
            if result.get("success"):
                candidates.append({
                    "strategy": s["name"],
                    "description": s["desc"],
                    "config": {"beam_width": s["beam_width"], "threshold": s["high_cross_threshold"]},
                    "assignments": result["assignments"],
                    "total_score": result["total_score"],
                    "assign_rate": result.get("stats", {}).get("assign_rate", 0),
                    "conflict_count": result.get("conflicts", {}).get("conflict_count", 0),
                    "unassigned": result.get("stats", {}).get("unassigned", 0),
                })
                _log.info("  ✅ %s: %s%% assigned, conflicts=%d",
                          s["name"], result.get("stats", {}).get("assign_rate", 0),
                          result.get("conflicts", {}).get("conflict_count", 0))
            else:
                _log.warning("  ❌ %s: %s", s["name"], result.get("error"))
        except Exception as e:
            _log.warning("  ❌ %s: %s", s["name"], e)

    return _rank_candidates(candidates)


def _rank_candidates(candidates: list[dict]) -> list[dict]:
    """综合评价候选方案，按分数排序。"""
    for c in candidates:
        assign_rate = c.get("assign_rate", 0) / 100.0
        conflict_penalty = c.get("conflict_count", 0) * 0.05
        unassigned_penalty = c.get("unassigned", 0) * 0.02

        score = assign_rate * 0.6 - conflict_penalty - unassigned_penalty
        score += c.get("total_score", 0) * 0.1
        c["composite_score"] = round(max(0, min(1, score)), 4)

    candidates.sort(key=lambda c: -c["composite_score"])

    for i, c in enumerate(candidates):
        c["rank"] = i + 1

    _log.info("综合评价完成:")
    for c in candidates:
        _log.info("  #%d %s: composite=%.3f assign=%s%% conflicts=%d",
                  c["rank"], c["strategy"], c["composite_score"],
                  c.get("assign_rate", 0), c.get("conflict_count", 0))

    return candidates
