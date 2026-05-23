"""教学任务模板组合枚举器。

针对实际排课场景，生成有意义的模板组合。
不是穷举所有数学解，而是产出排课实践中常见的分段时间模式。

每个模板段 = 固定的每周节数 × 持续周数。
一个模板组合 = 多个模板段的序列，按顺序填充学期（先密后疏）。
所有段的 week 之和 ≤ 学期总周数，不填满的周为该课程的空闲周。

组合的意义：教师在前 N 周遇到一种节奏，后 M 周切换到另一种，
而不是每周都在变。段数越少越稳定。
"""

from __future__ import annotations

from typing import Any

# ── 可调参数 ─────────────────────────────────────────────

WEEKLY_OPTIONS = [3, 2, 1]      # 允许的每周节数（降序，用于 w1≥w2 去重）
DEFAULT_TOTAL_WEEKS = 18           # 学期总周数
MIN_SEGMENT_WEEKS = 2              # 模板段最少持续几周
MAX_TOTAL = 30                     # 单任务最多生成多少种组合


def enumerate_templates(
    periods_needed: int,
    task_weeks: int | None = None,
    total_weeks: int = DEFAULT_TOTAL_WEEKS,
) -> list[list[dict[str, int]]]:
    """枚举教学任务的所有代表性模板组合。

    生成策略：
    1. 单段解：整学期一个节奏（最稳定）
    2. 双段解：前密后疏，最常见的节奏切换
    3. 三段解：仅在必要时使用
    4. 兜底：当前 GA 的 1×N + 零散模式

    Args:
        periods_needed: 需要排的节次数（总课时 ÷ 2）
        task_weeks: 教学任务实际有效周数（如 1-17 周则传 17）。
                    为 None 时自动用 min(total_weeks, periods_needed)。
        total_weeks: 学期总周数，默认 18。仅在 task_weeks 为 None 时使用。

    Returns:
        模板组合列表，最多 MAX_TOTAL 种。
    """
    if task_weeks is not None:
        total_weeks = task_weeks
    seen: set[tuple[tuple[int, int], ...]] = set()
    results: list[list[dict[str, int]]] = []

    def _add(segments: list[tuple[int, int]]) -> None:
        """去重添加"""
        segs = tuple(sorted(segments, key=lambda s: (-s[0], s[1])))
        if segs not in seen:
            seen.add(segs)
            results.append([{"weekly": s[0], "weeks": s[1]} for s in segs])

    # ── 1. 单段解 ──────────────────────────────────
    for w in WEEKLY_OPTIONS:
        if periods_needed % w == 0:
            weeks = periods_needed // w
            if MIN_SEGMENT_WEEKS <= weeks <= total_weeks:
                _add([(w, weeks)])

    # ── 2. 双段解 ── w1 ≥ w2 防对称 ──────────────
    for i, w1 in enumerate(WEEKLY_OPTIONS):
        for w2 in WEEKLY_OPTIONS[i:]:  # w1 >= w2
            if len(results) >= MAX_TOTAL:
                break
            for a in range(MIN_SEGMENT_WEEKS, total_weeks + 1):
                rem = periods_needed - a * w1
                if rem <= 0:
                    continue
                if rem % w2 != 0:
                    continue
                b = rem // w2
                if b < MIN_SEGMENT_WEEKS or b > total_weeks:
                    continue
                # 所有段的总周数 ≤ total_weeks（顺序填充）
                if a + b > total_weeks:
                    continue
                _add([(w1, a), (w2, b)])

    # ── 3. 三段解 ─────────────────────────────────
    for i, w1 in enumerate(WEEKLY_OPTIONS):
        for j, w2 in enumerate(WEEKLY_OPTIONS[i:]):
            for w3 in WEEKLY_OPTIONS[i + j:]:  # w1 ≥ w2 ≥ w3
                if len(results) >= MAX_TOTAL:
                    break
                if w1 == w2 == w3 == 1:
                    continue
                for a in range(MIN_SEGMENT_WEEKS, total_weeks + 1):
                    if a * w1 >= periods_needed:
                        break
                    for b in range(MIN_SEGMENT_WEEKS, total_weeks + 1 - a):
                        rem = periods_needed - a * w1 - b * w2
                        if rem <= 0:
                            continue
                        if rem % w3 != 0:
                            continue
                        c = rem // w3
                        if c < MIN_SEGMENT_WEEKS or c > total_weeks:
                            continue
                        if a + b + c > total_weeks:
                            continue
                        _add([(w1, a), (w2, b), (w3, c)])

    # ── 4. 兜底：当前 GA 模式 ── 1×N + 零散 ───────
    # 保证当前做法始终在候选池中
    base_weeks = min(total_weeks, periods_needed // 1)
    if base_weeks >= MIN_SEGMENT_WEEKS:
        _add([(1, base_weeks)])

    # ── 截断 ──────────────────────────────────────
    return results[:MAX_TOTAL]


# ── 辅助 ─────────────────────────────────────────────────


def template_summary(combinations: list[list[dict[str, int]]]) -> str:
    lines = [f"共 {len(combinations)} 种模板组合：", ""]
    for i, combo in enumerate(combinations, 1):
        parts = [f"{seg['weekly']}节/周×{seg['weeks']}周" for seg in combo]
        total = sum(seg["weekly"] * seg["weeks"] for seg in combo)
        lines.append(f"  {i:3d}. {' + '.join(parts)} = {total} periods")
    return "\n".join(lines)


def describe_templates(combinations: list[list[dict[str, int]]]) -> str:
    """季度的周分布描述"""
    lines = [f"共 {len(combinations)} 种模板组合", ""]
    for i, combo in enumerate(combinations, 1):
        cursor = 1
        parts = []
        for seg in combo:
            w = seg["weekly"]
            wk = seg["weeks"]
            end = cursor + wk - 1
            parts.append(f"周{cursor}-{end}: 每周{w}节")
            cursor += wk
        lines.append(f"  {i:2d}. {' → '.join(parts)}")
    return "\n".join(lines)


def combo_display(combo: list[dict[str, int]]) -> list[str]:
    return [f"{s['weekly']}×{s['weeks']}" for s in combo]


if __name__ == "__main__":
    for periods in [6, 8, 12, 18, 24, 36]:
        combos = enumerate_templates(periods)
        print(f"\nperiods_needed={periods:3d}  →  {len(combos):2d} 种")
        print(f"{'─'*60}")
        for i, combo in enumerate(combos):
            cursor = 1
            parts = []
            for seg in combo:
                w = seg["weekly"]
                wk = seg["weeks"]
                end = cursor + wk - 1
                parts.append(f"周{cursor:2d}-{end:2d}({w}节/周)")
                cursor += wk
            total = sum(s["weekly"] * s["weeks"] for s in combo)
            remain = DEFAULT_TOTAL_WEEKS - cursor + 1
            if remain > 0:
                parts.append(f"空闲{remain}周")
            print(f"  {i+1:2d}. {' + '.join(combo_display(combo)):16s}  →  {' + '.join(parts)}")
