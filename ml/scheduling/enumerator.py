"""模板集枚举器。

每个模板 = 1 节课/周 × 生效周列表。
模板集 = 若干模板的组合，所有模板的 lesson 之和 = total_lessons。

约束：模板的 weeks 只能来自 available_weeks。
"""

from __future__ import annotations
import logging
import time
from itertools import product
from functools import lru_cache
from ml.scheduling.types import Template, TemplateSet, weeks_to_mask

logger = logging.getLogger("ga")

MIN_TEMPLATE_WEEKS = 2
MAX_TEMPLATES = 4
MAX_COMBOS = 100


def enumerate_template_sets(
    total_lessons: int,
    available_weeks: list[int] | None = None,
) -> list[TemplateSet]:
    """为一个教学任务枚举所有模板集候选。

    每个模板集 = N 个模板。每个模板负责 1 节课/周 × weeks_list。
    所有模板的 len(weeks_list) 之和 = total_lessons。
    """
    pool = tuple(sorted(set(available_weeks))) if available_weeks is not None else tuple(range(1, 19))
    started_at = time.perf_counter()
    before = _enumerate_template_sets_cached.cache_info()
    results = list(_enumerate_template_sets_cached(total_lessons, pool))
    after = _enumerate_template_sets_cached.cache_info()
    cache_state = "hit" if after.hits > before.hits else "miss"
    logger.info(
        "Enumerated template sets: total_lessons=%s available_weeks=%s..%s count=%s cache=%s elapsed_ms=%.1f",
        total_lessons,
        pool[0] if pool else "?",
        pool[-1] if pool else "?",
        len(results),
        cache_state,
        (time.perf_counter() - started_at) * 1000,
    )
    return results


@lru_cache(maxsize=128)
def _enumerate_template_sets_cached(
    total_lessons: int,
    pool: tuple[int, ...],
) -> tuple[TemplateSet, ...]:
    pool_list = list(pool)

    avail = len(pool_list)

    seen: set[tuple] = set()
    results: list[TemplateSet] = []

    if total_lessons <= 0 or avail <= 0:
        return ()

    min_template_weeks = min(MIN_TEMPLATE_WEEKS, total_lessons)
    max_t = min(MAX_TEMPLATES, max(1, total_lessons // min_template_weeks))
    min_t = max(1, (total_lessons + avail - 1) // avail)

    for t_count in range(min_t, max_t + 1):
        _enum_for_count(t_count, total_lessons, pool_list, min_template_weeks, seen, results)

    results.sort(key=lambda ts: ts.penalty)
    logger.debug(
        "Template enumeration summary: total_lessons=%s t_range=%s..%s combos_before_cap=%s",
        total_lessons, min_t, max_t, len(results),
    )
    return tuple(results[:MAX_COMBOS])


def _enum_for_count(
    t_count: int,
    total: int,
    pool: list[int],
    min_template_weeks: int,
    seen: set,
    results: list[TemplateSet],
) -> None:
    avail = len(pool)

    def _recurse(remaining: int, current: list[int], depth: int):
        if depth == t_count - 1:
            if remaining < min_template_weeks or remaining > avail:
                return
            lengths = tuple(sorted(current + [remaining]))
            _build_template_sets(lengths, pool, seen, results)
            return

        max_w = min(avail, remaining - (t_count - depth - 1) * min_template_weeks)
        min_w = max(min_template_weeks, remaining - (t_count - depth - 1) * avail)
        for w in range(min_w, max_w + 1):
            _recurse(remaining - w, current + [w], depth + 1)

    _recurse(total, [], 0)


def _build_template_sets(
    lengths: tuple[int, ...],
    pool: list[int],
    seen: set,
    results: list[TemplateSet],
) -> None:
    pattern_options = [_week_patterns(length, pool) for length in lengths]

    for combo in product(*pattern_options):
        signature = tuple(sorted(tuple(weeks) for weeks in combo))
        if signature in seen:
            continue
        seen.add(signature)
        templates = [
            Template(week_mask=weeks_to_mask(list(weeks)), weeks_list=list(weeks))
            for weeks in signature
        ]
        penalty = _score_template_set(templates, sum(lengths), pool)
        results.append(TemplateSet(templates=templates, penalty=penalty))


def _week_patterns(count: int, pool: list[int]) -> list[tuple[int, ...]]:
    """Generate early, late, centered, and evenly-spread week patterns."""
    if count >= len(pool):
        return [tuple(pool)]

    candidates: list[list[int]] = []
    candidates.append(pool[:count])
    candidates.append(pool[-count:])

    start = max(0, (len(pool) - count) // 2)
    candidates.append(pool[start:start + count])

    if count == 1:
        candidates.append([pool[len(pool) // 2]])
    else:
        step = (len(pool) - 1) / (count - 1)
        indexes = [round(i * step) for i in range(count)]
        candidates.append([pool[i] for i in indexes])

    for offset in range(min(2, len(pool))):
        sparse = pool[offset::2][:count]
        if len(sparse) == count:
            candidates.append(sparse)

    seen: set[tuple[int, ...]] = set()
    patterns: list[tuple[int, ...]] = []
    for weeks in candidates:
        pattern = tuple(sorted(set(weeks)))
        if len(pattern) != count or pattern in seen:
            continue
        seen.add(pattern)
        patterns.append(pattern)

    return patterns


def _score_template_set(
    templates: list[Template],
    total_lessons: int,
    available_weeks: list[int] | None = None,
) -> float:
    """模板集评分：段数 + 均匀性 + 连续性"""
    n = len(templates)
    seg_pen = 20 * n
    pool = available_weeks or list(range(1, 19))

    # 每周课次方差（越小越均匀）。必须把可用但未排课的周也算进去，
    # 否则 24 次课会被压到两个 12 周模板里，留下大量空周。
    weekly_load_by_week = {week: 0 for week in pool}
    for t in templates:
        for wn in t.weeks_list:
            if wn in weekly_load_by_week:
                weekly_load_by_week[wn] += 1
    all_loads = list(weekly_load_by_week.values())
    if all_loads:
        mean = total_lessons / len(all_loads)
        var = sum((v - mean) ** 2 for v in all_loads) / len(all_loads)
        var_pen = 10 * var
    else:
        var_pen = 0

    expected_active_weeks = min(total_lessons, len(pool))
    active_week_count = sum(1 for value in all_loads if value > 0)
    coverage_pen = 100 * max(0, expected_active_weeks - active_week_count)

    # 连续性：检查是否有大空洞
    active_weeks = [week for week, load in weekly_load_by_week.items() if load > 0]
    if len(active_weeks) > 1:
        gaps = [active_weeks[i + 1] - active_weeks[i] for i in range(len(active_weeks) - 1)]
        max_gap = max(gaps)
        discontinuity = 30 * max(0, max_gap - 2)  # 间隔 > 2 周才扣
    else:
        discontinuity = 0

    if active_weeks:
        target_center = (min(pool) + max(pool)) / 2
        active_center = sum(active_weeks) / len(active_weeks)
        balance_pen = 2 * abs(active_center - target_center)
    else:
        balance_pen = 0

    return seg_pen + var_pen + coverage_pen + discontinuity + balance_pen
