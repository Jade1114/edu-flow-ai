"""GA 模板适配层（v3）。

模板 = 1 节课/周 × 生效周列表。
一个教学任务 = 多个模板的组合（覆盖总课时）。
GA 负责：① 选模板组合  ② 每个模板填 (day, period, classroom)

个体编码（定长，每任务 1+MAX_TEMPLATES 个基因）：
  [combo_0, tmpl0_slot_0, tmpl1_slot_0, ..., tmpl5_slot_0,
   combo_1, tmpl0_slot_1, ...]
  模板数不足 MAX_TEMPLATES 的，多余 slot 基因忽略。
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Any

from ml.scheduling.template.enumerator import enumerate_template_combos
from ml.scheduling.infra.constants import TOTAL_WEEKS
from ml.scheduling.infra.runtime import log_chain

# 每个任务预留的最大模板数
MAX_TEMPLATES = 6


# ── 候选池构建 ──────────────────────────────────────────

def build_pools(
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    rng: random.Random,
) -> tuple[list[list[list[dict[str, Any]]]], list[list[dict[str, Any]]]]:
    """构建模板组合池 + slot 候选池。

    Returns:
        combo_pools: [task0的combos, task1的combos, ...]
          每个 combo = [template0, template1, ...]
          每个 template = {"weeks": N, "weeks_list": [int]}
        candidate_pools: [task0的slot候选, task1的slot候选, ...]
          每个候选 = {"day": int, "period": int, "classroom_id": int}
    """
    unique_weeks = sorted(set(int(s["week_number"]) for s in time_slots))
    log_chain("build_pools 可用周", {"weeks": unique_weeks, "count": len(unique_weeks)})

    combo_pools: list[list[list[dict[str, Any]]]] = []
    candidate_pools: list[list[dict[str, Any]]] = []

    for task in tasks:
        tid = int(task["teaching_task_id"])
        periods = int(task.get("total_hours") or 0) // 2
        if periods <= 0:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        # 枚举模板组合
        combos = enumerate_template_combos(periods, available_weeks=unique_weeks)
        if not combos:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        # slot 候选
        cands = _build_candidate_slots(task, classrooms, time_slots)
        if not cands:
            combo_pools.append([])
            candidate_pools.append([])
            continue

        # 日志
        if len(combo_pools) < 5:
            sample = []
            for ci, c in enumerate(combos[:3]):
                segs = [f"T{j}: 周{t['weeks_list'][0]}-{t['weeks_list'][-1]}({len(t['weeks_list'])}周)" for j, t in enumerate(c)]
                sample.append(f"[{ci}] " + " + ".join(segs))
            log_chain("任务模板", {"task_id": tid, "periods": periods, "combo数": len(combos), "样例": sample})

        combo_pools.append(combos)
        candidate_pools.append(cands)

    return combo_pools, candidate_pools


def _build_candidate_slots(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required = task.get("required_room_type") or ""
    students = int(task.get("total_student_count") or 0)
    valid_rooms = [r for r in classrooms if int(r.get("capacity") or 0) >= students]
    if required:
        valid_rooms = [r for r in valid_rooms if required.strip().lower() == (r.get("classroom_type") or "").strip().lower()]
    if not valid_rooms or not time_slots:
        return []

    slots_set = {(int(s["day_of_week"]), int(s["period_index"])) for s in time_slots}
    cands = []
    for day, period in sorted(slots_set):
        for room in valid_rooms:
            cands.append({"day": day, "period": period, "classroom_id": int(room["id"])})
    return cands


# ── 个体编码 ─────────────────────────────────────────────

def individual_len(task_count: int) -> int:
    return task_count * (1 + MAX_TEMPLATES)


def _decode(
    individual: list[int],
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """解码为每周分配列表"""
    assigns: list[dict[str, Any]] = []

    for ti in range(len(combo_pools)):
        base = ti * (1 + MAX_TEMPLATES)
        combo_idx = individual[base]
        combos = combo_pools[ti]
        cands = candidate_pools[ti]

        if not combos or not cands or combo_idx < 0 or combo_idx >= len(combos):
            continue

        combo = combos[combo_idx]
        for tj, tmpl in enumerate(combo):
            gene_idx = base + 1 + tj
            if gene_idx >= len(individual):
                break
            cand_idx = individual[gene_idx]
            if cand_idx < 0 or cand_idx >= len(cands):
                continue
            cand = cands[cand_idx]

            for wn in tmpl["weeks_list"]:
                assigns.append({
                    "week": wn,
                    "day": cand["day"],
                    "period": cand["period"],
                    "classroom_id": cand["classroom_id"],
                    "task_id": ti,
                    "template_idx": tj,
                })

    return assigns


# ── GA 接口 ─────────────────────────────────────────────


def random_individual(
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
    rng: random.Random,
) -> list[int]:
    n = individual_len(len(combo_pools))
    ind = [0] * n
    for ti in range(len(combo_pools)):
        base = ti * (1 + MAX_TEMPLATES)
        if combo_pools[ti]:
            ind[base] = rng.randrange(len(combo_pools[ti]))
        for tj in range(MAX_TEMPLATES):
            if candidate_pools[ti]:
                ind[base + 1 + tj] = rng.randrange(len(candidate_pools[ti]))
    return ind


def evaluate(
    individual: list[int],
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    assigns = _decode(individual, combo_pools, candidate_pools)

    # 冲突检测：(week, day, period) 只能被一个 template 占用
    usage: dict[tuple[int, int, int], int] = Counter()
    for a in assigns:
        usage[(a["week"], a["day"], a["period"])] += 1

    conflicts = sum(max(0, c - 1) for c in usage.values())

    weeks_set = set(a["week"] for a in assigns)

    # 每个任务的课时完整度
    fitness = -conflicts * 1000

    return {
        "fitness": fitness,
        "hard_conflict_count": conflicts,
        "assignments": len(assigns),
        "weeks_covered": len(weeks_set),
    }


def crossover(
    parent_a: list[int],
    parent_b: list[int],
    rng: random.Random,
) -> list[int]:
    n = len(parent_a)
    if n <= 1:
        return parent_a[:]
    pt = rng.randrange(1, n)
    return parent_a[:pt] + parent_b[pt:]


def mutate(
    individual: list[int],
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
    rate: float,
    rng: random.Random,
) -> list[int]:
    result = individual[:]
    for ti in range(len(combo_pools)):
        base = ti * (1 + MAX_TEMPLATES)
        if rng.random() < rate and combo_pools[ti]:
            result[base] = rng.randrange(len(combo_pools[ti]))
        for tj in range(MAX_TEMPLATES):
            if rng.random() < rate and candidate_pools[ti]:
                result[base + 1 + tj] = rng.randrange(len(candidate_pools[ti]))
    return result


def tournament_select(
    scored: list[dict[str, Any]],
    size: int,
    rng: random.Random,
) -> list[int]:
    selected = [scored[rng.randrange(len(scored))] for _ in range(size)]
    selected.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return selected[0]["individual"]


def evolve(
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
    rng: random.Random,
    *,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
) -> list[dict[str, Any]]:
    pop = [random_individual(combo_pools, candidate_pools, rng) for _ in range(population_size)]

    for gen in range(1, generations + 1):
        scored = [{"individual": ind, "metrics": evaluate(ind, combo_pools, candidate_pools)} for ind in pop]
        scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)

        if gen == 1 or gen == generations or gen % 10 == 0:
            m = scored[0]["metrics"]
            log_chain(f"Gen {gen}", {
                "fitness": m["fitness"], "conflicts": m["hard_conflict_count"],
                "assigns": m["assignments"], "weeks": m["weeks_covered"],
            })

        elite = max(1, min(elite_size, len(scored)))
        nxt = [item["individual"][:] for item in scored[:elite]]

        while len(nxt) < population_size:
            p1 = tournament_select(scored, tournament_size, rng)
            p2 = tournament_select(scored, tournament_size, rng)
            child = crossover(p1, p2, rng)
            child = mutate(child, combo_pools, candidate_pools, mutation_rate, rng)
            nxt.append(child)

        pop = nxt

    scored = [{"individual": ind, "metrics": evaluate(ind, combo_pools, candidate_pools)} for ind in pop]
    scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return scored


# ── 输出展开 ─────────────────────────────────────────────


def _time_slot_id(week: int, day: int, period: int) -> int:
    return (week - 1) * 35 + (day - 1) * 5 + period


def to_rows(
    individual: list[int],
    combo_pools: list[list[list[dict[str, Any]]]],
    candidate_pools: list[list[dict[str, Any]]],
    tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seq = 0

    for ti in range(len(combo_pools)):
        base = ti * (1 + MAX_TEMPLATES)
        combo_idx = individual[base]
        combos = combo_pools[ti]
        cands = candidate_pools[ti]

        if not combos or not cands or combo_idx < 0 or combo_idx >= len(combos):
            continue

        combo = combos[combo_idx]
        tid = tasks[ti].get("teaching_task_id") if tasks else None
        teacher_id = tasks[ti].get("teacher_id") if tasks else None
        teacher_name = tasks[ti].get("teacher_name", "") if tasks else ""

        for tj, tmpl in enumerate(combo):
            gene_idx = base + 1 + tj
            if gene_idx >= len(individual):
                break
            cand_idx = individual[gene_idx]
            if cand_idx < 0 or cand_idx >= len(cands):
                continue
            cand = cands[cand_idx]

            for wn in tmpl["weeks_list"]:
                seq += 1
                rows.append({
                    "sequence": seq,
                    "teaching_task_id": tid,
                    "teacher_id": teacher_id,
                    "teacher_name": teacher_name,
                    "fragment_index": tj,
                    "classroom_id": cand["classroom_id"],
                    "time_slot_id": _time_slot_id(wn, cand["day"], cand["period"]),
                    "week_number": wn,
                    "day_of_week": cand["day"],
                    "period_index": cand["period"],
                    "predicted_score": 0.0,
                    "rule_score": 0.0,
                    "has_hard_conflict": 0,
                    "reject_reason": "",
                    "teacher_profile_penalty": 0.0,
                    "teacher_profile_penalty_explanation": "",
                    "teacher_profile_penalty_breakdown": "[]",
                })

    return rows
