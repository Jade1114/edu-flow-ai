"""教学任务模板组合枚举器。

针对实际排课场景，生成有意义的模板组合。
不是穷举所有数学解，而是产出排课实践中常见的分段时间模式。

每个模板段 = 固定的每周节数 × 持续周数 × 具体生效周列表。
一个模板组合 = 多个模板段的序列，按周列表顺序填充。
所有段的 weeks_list 不重叠，且均为 available_weeks 的子集。
所有段的总节数 = periods_needed。
"""

from __future__ import annotations

from typing import Any

# ── 可调参数 ─────────────────────────────────────────────

WEEKLY_OPTIONS = [3, 2, 1]      # 允许的每周节数（降序，用于 w1≥w2 去重）
DEFAULT_TOTAL_WEEKS = 18           # 学期总周数
MIN_SEGMENT_WEEKS = 2              # 模板段最少持续几周
MAX_TOTAL = 100                    # 单任务最多生成多少种组合


def enumerate_templates(
    periods_needed: int,
    available_weeks: list[int] | None = None,
) -> list[list[dict[str, Any]]]:
    """枚举教学任务的所有代表性模板组合。

    模板段结构：
      {"weekly": int, "weeks": int, "weeks_list": list[int]}
      weekly - 每周几节
      weeks - weeks_list 的长度
      weeks_list - 具体在哪几周生效

    Args:
        periods_needed: 需要排的节次数（总课时 ÷ 2）
        available_weeks: 教学任务可用的周列表，如 [1,2,...,17]。
                         为 None 时默认 1-18 周。

    Returns:
        模板组合列表，每组合是 TemplateSegment 的列表。
    """
    if available_weeks is not None:
        weeks_pool = sorted(set(available_weeks))
        avail_count = len(weeks_pool)
    else:
        weeks_pool = list(range(1, DEFAULT_TOTAL_WEEKS + 1))
        avail_count = DEFAULT_TOTAL_WEEKS

    seen: set[tuple[tuple[int, int], ...]] = set()
    results: list[list[dict[str, Any]]] = []

    def _slice(start: int, count: int) -> list[int]:
        end = min(start + count, avail_count)
        return weeks_pool[start:end]

    def _make_seg(weekly: int, start: int, count: int) -> tuple[int, int, list[int]]:
        wl = _slice(start, count)
        return (weekly, len(wl), wl)

    def _add(segments: list[tuple[int, int, list[int]]]) -> None:
        dedup_key = tuple(sorted([(s[0], s[1]) for s in segments], key=lambda x: (-x[0], x[1])))
        if dedup_key not in seen:
            seen.add(dedup_key)
            results.append([{"weekly": s[0], "weeks": s[1], "weeks_list": s[2]} for s in segments])

    def _total_periods(segs: list[tuple[int, int, list[int]]]) -> int:
        return sum(w * len(wl) for w, _, wl in segs)

    # ── 1. 单段解 ──────────────────────────────────
    for w in WEEKLY_OPTIONS:
        if periods_needed % w == 0:
            wk = periods_needed // w
            if MIN_SEGMENT_WEEKS <= wk <= avail_count:
                _add([_make_seg(w, 0, wk)])

    # ── 2. 双段解 ─────────────────────────────────
    for i, w1 in enumerate(WEEKLY_OPTIONS):
        for w2 in WEEKLY_OPTIONS[i:]:
            if len(results) >= MAX_TOTAL:
                break
            for a in range(MIN_SEGMENT_WEEKS, avail_count + 1):
                rem = periods_needed - a * w1
                if rem <= 0:
                    continue
                if rem % w2 != 0:
                    continue
                b = rem // w2
                if b < MIN_SEGMENT_WEEKS or b > avail_count - a:
                    continue
                s1 = _make_seg(w1, 0, a)
                s2 = _make_seg(w1, a, b)  # w2 的 slot 由后面排序保证
                # 这里用 w2 做第二段
                s2_fixed = (w2, s2[1], s2[2])
                if _total_periods([s1, s2_fixed]) != periods_needed:
                    continue
                _add([s1, s2_fixed])

    # ── 3. 三段解 ─────────────────────────────────
    for i, w1 in enumerate(WEEKLY_OPTIONS):
        for j, w2 in enumerate(WEEKLY_OPTIONS[i:]):
            for w3 in WEEKLY_OPTIONS[i + j:]:
                if len(results) >= MAX_TOTAL:
                    break
                if w1 == w2 == w3 == 1:
                    continue
                for a in range(MIN_SEGMENT_WEEKS, avail_count + 1):
                    if a * w1 >= periods_needed:
                        break
                    for b in range(MIN_SEGMENT_WEEKS, avail_count + 1 - a):
                        rem = periods_needed - a * w1 - b * w2
                        if rem <= 0:
                            continue
                        if rem % w3 != 0:
                            continue
                        c = rem // w3
                        if c < MIN_SEGMENT_WEEKS or c > avail_count - a - b:
                            continue
                        s1 = _make_seg(w1, 0, a)
                        s2 = _make_seg(w2, a, b)
                        s3 = _make_seg(w3, a + b, c)
                        if _total_periods([s1, s2, s3]) != periods_needed:
                            continue
                        _add([s1, s2, s3])

    # ── 4. 兜底：1×N ──────────────────────────────
    base_wk = min(avail_count, periods_needed // 1)
    if base_wk >= MIN_SEGMENT_WEEKS:
        _add([_make_seg(1, 0, base_wk)])

    return results[:MAX_TOTAL]


# ── 辅助 ─────────────────────────────────────────────────


def template_summary(combinations: list[list[dict[str, Any]]]) -> str:
    lines = [f"共 {len(combinations)} 种模板组合：", ""]
    for i, combo in enumerate(combinations, 1):
        parts = [f"{seg['weekly']}节/周×{seg['weeks']}周" for seg in combo]
        total = sum(seg["weekly"] * seg["weeks"] for seg in combo)
        lines.append(f"  {i:3d}. {' + '.join(parts)} = {total} periods")
    return "\n".join(lines)


def describe_templates(combinations: list[list[dict[str, Any]]]) -> str:
    lines = [f"共 {len(combinations)} 种模板组合", ""]
    for i, combo in enumerate(combinations, 1):
        parts = []
        for seg in combo:
            wl = seg["weeks_list"]
            w = seg["weekly"]
            if wl:
                parts.append(f"周{wl[0]}-{wl[-1]}: 每周{w}节")
        lines.append(f"  {i:2d}. {' → '.join(parts)}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 演示：18 周 和 17 周的区别
    for label, aw in [("1-18 周", None), ("1-17 周", list(range(1, 18)))]:
        print(f"\n{'='*60}")
        print(f"available_weeks = {label}")
        print(f"{'='*60}")
        for periods in [12, 18, 24, 36]:
            combos = enumerate_templates(periods, available_weeks=aw)
            cursor = 1
            parts = []
            for seg in combos[0]:
                wl = seg["weeks_list"]
                parts.append(f"周{wl[0]}-{wl[-1]}({seg['weekly']}节/周)")
            total = sum(s["weekly"] * s["weeks"] for s in combos[0])
            print(f"  {periods:3d} periods → {len(combos):2d} 种  "
                  f"例: {' + '.join(parts)} = {total}")
