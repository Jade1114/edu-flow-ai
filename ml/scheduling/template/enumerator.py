"""教学任务模板组合枚举器（v3）。

核心规则：
  一个模板 = 1 节课/周 × 生效周列表。
  一个任务需要多个模板组合起来覆盖总课时。
  多个模板可在同一周重叠（重叠则该周有多节课）。

模板结构：
  {"task_id": int, "weeks_list": [int], ...}
  其中 slot/classroom 由 GA 填充，不在枚举器内决定。
"""

from __future__ import annotations

from typing import Any

# ── 可调参数 ─────────────────────────────────────────────

MIN_TEMPLATE_WEEKS = 2          # 一个模板最少覆盖几周
MAX_TEMPLATES = 6               # 一个任务最多套几个模板
MAX_COMBOS = 100                # 最多返回多少种组合
DEFAULT_WEEKS = 18


def enumerate_template_combos(
    periods_needed: int,
    available_weeks: list[int] | None = None,
) -> list[list[dict[str, Any]]]:
    """枚举一个教学任务的所有模板组合。

    每个组合 = 若干模板的列表。每个模板负责 1 节课/周。
    所有模板的 weeks_list 长度之和 = periods_needed。

    Args:
        periods_needed: 需要的节次数（总课时 ÷ 2）
        available_weeks: 可用周列表，如 [2,3,...,17]

    Returns:
        [[{task_id, weeks_list, ...}], ...]
    """
    if available_weeks is not None:
        weeks_pool = sorted(set(available_weeks))
    else:
        weeks_pool = list(range(1, DEFAULT_WEEKS + 1))

    avail = len(weeks_pool)

    def _wl(count: int) -> list[int]:
        """取前 count 个周"""
        end = min(count, avail)
        return weeks_pool[:end]

    seen: set[tuple] = set()
    results: list[list[dict[str, Any]]] = []

    def _add(weeks_lengths: list[int]) -> None:
        key = tuple(sorted(weeks_lengths))
        if key in seen:
            return
        seen.add(key)
        combos = []
        for wl_len in weeks_lengths:
            combos.append({
                "weeks": wl_len,
                "weeks_list": _wl(wl_len),
            })
        results.append(combos)

    # ── 枚举 ─────────────────────────────────────────
    # N 个模板，每个模板覆盖 w_i 周，sum(w_i) = periods_needed
    # w_i ∈ [MIN_TEMPLATE_WEEKS, avail]
    # N ∈ [max(1, ceil(P/avail)), min(MAX_TEMPLATES, P/MIN_TEMPLATE_WEEKS)]

    max_t = min(MAX_TEMPLATES, periods_needed // MIN_TEMPLATE_WEEKS)
    min_t = max(1, (periods_needed + avail - 1) // avail)  # ceil

    for t_count in range(min_t, max_t + 1):
        if len(results) >= MAX_COMBOS:
            break
        _enumerate_for_count(t_count, periods_needed, avail, _add, results)

    return results[:MAX_COMBOS]


def _enumerate_for_count(
    t_count: int,
    periods_needed: int,
    avail: int,
    add_fn,
    results: list,
) -> None:
    """枚举 N 个模板的 length 分布"""
    # 递归分配剩余 period 到每个模板
    def _recurse(remaining: int, slots: int, current: list[int], depth: int):
        if len(results) >= MAX_COMBOS:
            return
        if depth == t_count - 1:
            # 最后一个模板必须恰好覆盖剩余的 period
            if remaining < MIN_TEMPLATE_WEEKS or remaining > avail:
                return
            add_fn(current + [remaining])
            return
        # 当前模板的可选长度
        max_w = min(avail, remaining - (t_count - depth - 1) * MIN_TEMPLATE_WEEKS)
        min_w = max(MIN_TEMPLATE_WEEKS, remaining - (t_count - depth - 1) * avail)
        for w in range(min_w, max_w + 1):
            _recurse(remaining - w, slots, current + [w], depth + 1)

    _recurse(periods_needed, avail, [], 0)


# ── 辅助 ─────────────────────────────────────────────────


def combo_summary(combos: list[list[dict[str, Any]]]) -> str:
    lines = [f"共 {len(combos)} 种模板组合", ""]
    for i, combo in enumerate(combos[:20], 1):
        parts = []
        for j, tmpl in enumerate(combo):
            wl = tmpl["weeks_list"]
            parts.append(f"模板{j+1}: {len(wl)}周 周{wl[0]}-{wl[-1]}")
        total = sum(len(t["weeks_list"]) for t in combo)
        lines.append(f"  {i:2d}. {' + '.join(parts)} = {total}节")
    if len(combos) > 20:
        lines.append(f"  ... 还有 {len(combos) - 20} 种")
    return "\n".join(lines)


if __name__ == "__main__":
    for periods, label in [(12, "1-18周"), (24, "1-18周"), (24, "2-17周(16周可用)"), (36, "1-18周")]:
        aw = list(range(2, 18)) if "2-17" in label else None
        combos = enumerate_template_combos(periods, available_weeks=aw)
        if combos:
            first = combos[0]
            parts = [f"模板{j+1}: {len(t['weeks_list'])}周" for j, t in enumerate(first)]
            print(f"\n{periods}periods, {label} → {len(combos):2d} 种 例: {' + '.join(parts)}")
            for c in combos[:5]:
                detail = [f"模板{j+1}: 周{t['weeks_list'][0]}-{t['weeks_list'][-1]}" for j, t in enumerate(c)]
                print(f"    {' + '.join(detail)}")
