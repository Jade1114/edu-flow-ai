"""GA 模板适配层：连接枚举器与 GA 主流程。

模板 = 教学任务的周节奏（每周几节 × 持续几周），不包含具体 slot。
GA 负责：① 选哪个模板组合  ② 每个段填什么 (day, period, classroom)

个体结构（定长，每任务 1+MAX_SEGMENTS 个基因）：
  [combo_0, seg0_0, seg1_0, seg2_0,  combo_1, seg0_1, ...]
  其中 combo 基因范围 = 0..N-1 种模板组合
  seg 基因范围 = 0..候选 (day,period,classroom) 数-1
  模板段数不足 MAX_SEGMENTS 的，多余 seg 基因忽略。
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from ml.scheduling.template.enumerator import enumerate_templates
from ml.scheduling.infra.constants import TOTAL_WEEKS
from ml.scheduling.infra.runtime import log_chain

# 每个任务预留的最大段数（与枚举器 MAX_SEGMENTS 一致）
MAX_SEGMENTS = 3


# ── 候选池构建 ──────────────────────────────────────────


def build_pools(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    """构建模板节奏池 + 每任务的 slot 候选池。

    Returns:
        combo_pools: 每任务一个 combo_[info, ...] 列表
        task_candidate_pools: 每任务的 slot 候选 [(day, period, classroom), ...]
    """
    combo_pools: list[list[dict[str, Any]]] = []
    candidate_pools: list[list[dict[str, Any]]] = []

    # 日志：从 time_slots 提取的可用周
    unique_weeks = sorted(set(int(s["week_number"]) for s in time_slots))
    log_chain("build_pools 可用周", {"weeks": unique_weeks, "count": len(unique_weeks)})

    for task in tasks:
        tid = int(task["teaching_task_id"])
        periods = int(task.get("total_hours") or 0) // 2
        if periods <= 0:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        # 1. 枚举模板节奏
        combos = enumerate_templates(periods, available_weeks=unique_weeks)
        if not combos:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        # 2. 构建 slot 候选
        cands = _build_candidate_slots(task, classrooms, time_slots)
        if not cands:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        combo_pools.append(combos)
        candidate_pools.append(cands)

    return combo_pools, candidate_pools


def _build_candidate_slots(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """构建 (day, period, classroom) 候选（简化版：无需预填充阵容）"""
    required_room_type = task.get("_required_room_type") or task.get("required_room_type") or ""
    total_student_count = int(task.get("total_student_count") or 0)
    valid_rooms = [
        r for r in classrooms
        if int(r.get("capacity") or 0) >= total_student_count
    ]
    if required_room_type:
        valid_rooms = [
            r for r in valid_rooms
            if (required_room_type.strip().lower() == (r.get("classroom_type") or "").strip().lower())
        ]
    if not valid_rooms or not time_slots:
        return []

    slots_set: set[tuple[int, int]] = set()
    for s in time_slots:
        slots_set.add((int(s["day_of_week"]), int(s["period_index"])))

    cands: list[dict[str, Any]] = []
    for day, period in sorted(slots_set):
        for room in valid_rooms:
            cands.append({
                "day": day,
                "period": period,
                "classroom_id": int(room["id"]),
            })
    return cands


# ── 个体编码 ─────────────────────────────────────────────

# 个体定长 = (任务数) × (1 + MAX_SEGMENTS)
# 每个任务: [combo_idx, seg0_idx, seg1_idx, seg2_idx]
# combo_idx 范围: [0, combo_count)
# seg_idx 范围: [0, candidate_count)
# 如果 combo 的段数 < MAX_SEGMENTS，多余的 seg_idx 被忽略


def individual_length(task_count: int) -> int:
    return task_count * (1 + MAX_SEGMENTS)


def _decode_individual(
    individual: list[int],
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    total_weeks: int = TOTAL_WEEKS,
) -> list[dict[str, Any]]:
    """将个体解码为展开的每周分配列表。

    返回 [{week, day, period, classroom_id, task_id, teacher_id}, ...]
    """
    assignments: list[dict[str, Any]] = []

    for task_idx in range(len(combo_pools)):
        base = task_idx * (1 + MAX_SEGMENTS)
        combo_idx = individual[base]
        combos = combo_pools[task_idx]
        cands = candidate_pools[task_idx]

        if not combos or not cands:
            continue
        if combo_idx < 0 or combo_idx >= len(combos):
            continue

        combo = combos[combo_idx]

        # 解码每个段
        week_cursor = 1
        for seg_i, seg in enumerate(combo):
            w = seg["weekly"]
            wk = seg["weeks"]
            seg_gene_idx = base + 1 + seg_i
            if seg_gene_idx >= len(individual):
                break
            cand_idx = individual[seg_gene_idx]
            if cand_idx < 0 or cand_idx >= len(cands):
                continue
            cand = cands[cand_idx]
            day = cand["day"]
            period = cand["period"]
            room = cand["classroom_id"]

            for week_off in range(wk):
                wn = week_cursor + week_off
                if wn > total_weeks:
                    break
                for p_off in range(w):
                    p = period + p_off
                    assignments.append({
                        "week": wn,
                        "day": day,
                        "period": p,
                        "classroom_id": room,
                        "task_id": task_idx,
                        "segment_idx": seg_i,
                    })
            week_cursor += wk

    return assignments


# ── GA 接口 ─────────────────────────────────────────────


def random_individual_template(
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    rng: random.Random,
) -> list[int]:
    """随机个体"""
    n_genes = individual_length(len(combo_pools))
    individual = [0] * n_genes
    for task_idx in range(len(combo_pools)):
        base = task_idx * (1 + MAX_SEGMENTS)
        combos = combo_pools[task_idx]
        cands = candidate_pools[task_idx]
        if combos:
            individual[base] = rng.randrange(len(combos))
        for seg_i in range(MAX_SEGMENTS):
            if cands:
                individual[base + 1 + seg_i] = rng.randrange(len(cands))
    return individual


def evaluate_individual_template(
    individual: list[int],
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    total_weeks: int = TOTAL_WEEKS,
) -> dict[str, Any]:
    """评估个体：展开 → 检测冲突 → 打分"""
    assignments = _decode_individual(individual, combo_pools, candidate_pools, total_weeks)

    # 冲突检测：同一个 (week, day, period) 不能被多个任务占用
    slot_usage: dict[tuple[int, int, int], list[int]] = {}
    for a in assignments:
        key = (a["week"], a["day"], a["period"])
        slot_usage.setdefault(key, []).append(a["task_id"])

    hard_conflict_count = 0
    for key, task_ids in slot_usage.items():
        if len(task_ids) > 1:
            hard_conflict_count += len(task_ids) - 1

    # 完整度：检查是否每个任务都填满了
    week_range = set(a["week"] for a in assignments)

    fitness = -hard_conflict_count * 1000 - (total_weeks - len(week_range)) * 10

    return {
        "fitness": fitness,
        "hard_conflict_count": hard_conflict_count,
        "assignments": len(assignments),
        "weeks_covered": len(week_range),
    }


def crossover_template(
    parent_a: list[int],
    parent_b: list[int],
    rng: random.Random,
) -> list[int]:
    """单点按任务交叉"""
    n = len(parent_a)
    if n <= 1:
        return parent_a[:]
    point = rng.randrange(1, n)
    child = parent_a[:point] + parent_b[point:]
    return child


def mutate_template(
    individual: list[int],
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    mutation_rate: float,
    rng: random.Random,
) -> list[int]:
    """变异：按概率重选 combo 或 seg 候选"""
    result = individual[:]
    for task_idx in range(len(combo_pools)):
        base = task_idx * (1 + MAX_SEGMENTS)
        combos = combo_pools[task_idx]
        cands = candidate_pools[task_idx]

        if rng.random() < mutation_rate and combos:
            result[base] = rng.randrange(len(combos))
        for seg_i in range(MAX_SEGMENTS):
            if rng.random() < mutation_rate and cands:
                result[base + 1 + seg_i] = rng.randrange(len(cands))
    return result


def tournament_select_template(
    scored: list[dict[str, Any]],
    tournament_size: int,
    rng: random.Random,
) -> list[int]:
    n = len(scored)
    if n == 0:
        return []
    selected = [scored[rng.randrange(n)] for _ in range(tournament_size)]
    selected.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return selected[0]["individual"]


def evolve_population_template(
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    rng: random.Random,
    *,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    total_weeks: int = TOTAL_WEEKS,
) -> list[dict[str, Any]]:
    population = [
        random_individual_template(combo_pools, candidate_pools, rng)
        for _ in range(population_size)
    ]

    for gen in range(1, generations + 1):
        scored = [
            {
                "individual": ind,
                "metrics": evaluate_individual_template(ind, combo_pools, candidate_pools, total_weeks),
            }
            for ind in population
        ]
        scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)

        if gen == 1 or gen == generations or gen % 5 == 0:
            m = scored[0]["metrics"]
            print(f"  Gen {gen:3d}: fitness={m['fitness']:.1f}, conflicts={m['hard_conflict_count']}, "
                  f"assignments={m['assignments']}, weeks={m['weeks_covered']}")

        elite_count = max(1, min(elite_size, len(scored)))
        next_pop = [item["individual"][:] for item in scored[:elite_count]]

        while len(next_pop) < population_size:
            p1 = tournament_select_template(scored, tournament_size, rng)
            p2 = tournament_select_template(scored, tournament_size, rng)
            child = crossover_template(p1, p2, rng)
            child = mutate_template(child, combo_pools, candidate_pools, mutation_rate, rng)
            next_pop.append(child)

        population = next_pop

    scored = [
        {
            "individual": ind,
            "metrics": evaluate_individual_template(ind, combo_pools, candidate_pools, total_weeks),
        }
        for ind in population
    ]
    scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return scored


# ── 输出展开 ─────────────────────────────────────────────


def _real_time_slot_id(week: int, day: int, period: int) -> int:
    return (week - 1) * 35 + (day - 1) * 5 + period


def individual_to_rows(
    individual: list[int],
    combo_pools: list[list[dict[str, Any]]],
    candidate_pools: list[list[dict[str, Any]]],
    tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """展开最优个体为兼容输出格式"""
    rows: list[dict[str, Any]] = []
    seq = 0

    for task_idx in range(len(combo_pools)):
        base = task_idx * (1 + MAX_SEGMENTS)
        combo_idx = individual[base]
        combos = combo_pools[task_idx]
        cands = candidate_pools[task_idx]

        if not combos or not cands or combo_idx < 0 or combo_idx >= len(combos):
            continue

        combo = combos[combo_idx]

        # 任务元信息
        task_id = None
        teacher_id = None
        teacher_name = ""
        if tasks and task_idx < len(tasks):
            task_id = tasks[task_idx].get("teaching_task_id")
            teacher_id = tasks[task_idx].get("teacher_id")
            teacher_name = tasks[task_idx].get("teacher_name") or ""

        week_cursor = 1
        for seg_i, seg in enumerate(combo):
            w = seg["weekly"]
            wk = seg["weeks"]
            seg_gene = base + 1 + seg_i
            if seg_gene >= len(individual):
                break
            cand_idx = individual[seg_gene]
            if cand_idx < 0 or cand_idx >= len(cands):
                continue
            cand = cands[cand_idx]
            day = cand["day"]
            period = cand["period"]
            room = cand["classroom_id"]

            for week_off in range(wk):
                wn = week_cursor + week_off
                for p_off in range(w):
                    p = period + p_off
                    seq += 1
                    rows.append({
                        "sequence": seq,
                        "teaching_task_id": task_id,
                        "teacher_id": teacher_id,
                        "teacher_name": teacher_name,
                        "fragment_index": seg_i,
                        "classroom_id": room,
                        "time_slot_id": _real_time_slot_id(wn, day, p),
                        "week_number": wn,
                        "day_of_week": day,
                        "period_index": p,
                        "predicted_score": 0.0,
                        "rule_score": 0.0,
                        "has_hard_conflict": 0,
                        "reject_reason": "",
                        "teacher_profile_penalty": 0.0,
                        "teacher_profile_penalty_explanation": "",
                        "teacher_profile_penalty_breakdown": "[]",
                    })
            week_cursor += wk

    return rows
