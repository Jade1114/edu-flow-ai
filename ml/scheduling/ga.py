"""GA 核心：初始化、适应度、交叉、变异、修复、进化。

染色体 = List[TaskGene]
交叉 = task-level uniform crossover
"""

from __future__ import annotations
import logging
import random
from collections import defaultdict
from typing import Any

_log = logging.getLogger("ga")

from ml.scheduling.assignment_scorer import AssignmentScorer
from ml.scheduling.teacher_profiles import profile_penalty
from ml.scheduling.types import (
    AllocationTask, TaskGene, TemplateAssignment,
    slot_to_day_period, weeks_overlap, mask_count,
)

# ── 参数 ──────────────────────────────────────────────────

HARD_CONFLICT_WEIGHT = 1_000_000
SAME_DAY_WEIGHT = 100
LATE_PERIOD_WEIGHT = 30
ML_SCORE_WEIGHT = 100
INIT_TOP_K = 20


# ── 贪心初始化（MRV：周数最长→课时最多→大教室） ────────


def init_population(
    tasks: list[AllocationTask],
    pop_size: int,
    rng: random.Random,
    scorer: AssignmentScorer | None = None,
) -> list[list[TaskGene]]:
    population = []
    for _ in range(pop_size):
        ind = _greedy_individual(tasks, rng, scorer)
        population.append(ind)
    return population


def _greedy_individual(
    tasks: list[AllocationTask],
    rng: random.Random,
    scorer: AssignmentScorer | None = None,
) -> list[TaskGene]:
    # MRV 排序：周数最长→课多→人多
    ordered = sorted(tasks, key=lambda t: (-mask_count(t.available_week_mask), -t.total_lessons, -t.student_count))

    genes: list[TaskGene] = []
    teachers_used: dict[tuple[int, int, int], int] = {}  # (teacher_id, week, slot_id) → task_id
    classes_used: dict[tuple[int, int, int], int] = {}  # (class_group_id, week, slot_id) → task_id
    rooms_used: dict[tuple[int, int, int], int] = {}  # (room_id, week, slot_id) → task_id

    for task in ordered:
        for ts_idx, ts in sorted(enumerate(task.template_sets), key=lambda item: item[1].penalty):
            temp_assigns = []
            for tmpl_idx, tmpl in enumerate(ts.templates):
                best_val = _pick_slot(task, tmpl_idx, tmpl, teachers_used, classes_used, rooms_used, rng, scorer)
                if best_val:
                    temp_assigns.append(best_val)
            if len(temp_assigns) == len(ts.templates):
                genes.append(TaskGene(
                    task_id=task.task_id,
                    template_set_id=ts_idx,
                    assignments=temp_assigns,
                ))
                # 记录占用
                for a in temp_assigns:
                    for wn in tmpl_yield(a.template_id, ts, task):
                        teachers_used[(task.teacher_id, wn, a.slot_id)] = task.task_id
                        for class_group_id in _task_class_group_ids(task):
                            classes_used[(class_group_id, wn, a.slot_id)] = task.task_id
                        rooms_used[(a.classroom_id, wn, a.slot_id)] = task.task_id
                break  # 模板集一旦选定，后续 GA 不再变更 template_set_id

    return genes


def _pick_slot(
    task: AllocationTask,
    tmpl_idx: int,
    tmpl,  # Template
    teachers_used: dict,
    classes_used: dict,
    rooms_used: dict,
    rng: random.Random,
    scorer: AssignmentScorer | None = None,
) -> TemplateAssignment | None:
    """为模板选 (slot, classroom) — hard/rule penalty + ML top-k 采样"""
    candidates = []
    for sid in task.candidate_slot_ids:
        for rid in task.candidate_room_ids:
            rule_penalty = _slot_room_penalty(sid, rid, tmpl, task, teachers_used, classes_used, rooms_used)
            ml_score = scorer.score(task, tmpl, sid, rid) if scorer else 0.0
            total_penalty = rule_penalty - ML_SCORE_WEIGHT * ml_score
            candidates.append((total_penalty, rule_penalty, -ml_score, sid, rid))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[1] >= HARD_CONFLICT_WEIGHT, x[0], x[2]))
    top = candidates[: min(INIT_TOP_K, len(candidates))]
    _total, _rule, _ml, sid, rid = rng.choice(top)
    return TemplateAssignment(template_id=tmpl_idx, slot_id=sid, classroom_id=rid)


def _slot_room_penalty(
    sid: int, rid: int, tmpl, task, teachers_used, classes_used, rooms_used,
) -> float:
    penalty = 0.0
    day, period = slot_to_day_period(sid)
    for wn in tmpl.weeks_list:
        if (task.teacher_id, wn, sid) in teachers_used:
            penalty += HARD_CONFLICT_WEIGHT
        for class_group_id in _task_class_group_ids(task):
            if (class_group_id, wn, sid) in classes_used:
                penalty += HARD_CONFLICT_WEIGHT
        if (rid, wn, sid) in rooms_used:
            penalty += HARD_CONFLICT_WEIGHT
    if period >= 4:  # late period
        penalty += LATE_PERIOD_WEIGHT
    profile_value, _ = profile_penalty(task.teacher_profile, sid)
    penalty += profile_value * len(tmpl.weeks_list)
    return penalty


def tmpl_yield(tmpl_idx: int, ts, task) -> list[int]:
    """返回模板的周列表（兼容 types.Template）"""
    from ml.scheduling.types import TemplateSet
    return ts.templates[tmpl_idx].weeks_list


def _task_class_group_ids(task: AllocationTask) -> tuple[int, ...]:
    class_group_ids = getattr(task, "class_group_ids", ()) or ()
    if class_group_ids:
        return tuple(int(cg) for cg in class_group_ids if int(cg) != 0)
    return (task.class_group_id,) if task.class_group_id != 0 else ()


# ── 适应度 ────────────────────────────────────────────────


def fitness(
    chromosome: list[TaskGene],
    tasks: list[AllocationTask],
    scorer: AssignmentScorer | None = None,
) -> dict[str, Any]:
    task_map = {t.task_id: t for t in tasks}
    ts_map = {t.task_id: t.template_sets for t in tasks}
    penalty = 0.0
    ml_score_total = 0.0
    hard = 0
    scheduled_task_ids: set[int] = set()
    duplicate_task_ids: set[int] = set()

    # 展开所有分配
    # (slot, week) → [(task_id, teacher_id, class_group_ids, room_id)]
    slot_week_usage: dict[tuple[int, int], list[tuple[int, int, tuple[int, ...], int]]] = defaultdict(list)
    all_assigns = []

    for gene in chromosome:
        task = task_map.get(gene.task_id)
        if not task:
            continue
        if gene.task_id in scheduled_task_ids:
            duplicate_task_ids.add(gene.task_id)
            hard += 1
            penalty += HARD_CONFLICT_WEIGHT
            continue
        scheduled_task_ids.add(gene.task_id)
        tss = ts_map.get(gene.task_id, [])
        ts = tss[gene.template_set_id] if gene.template_set_id < len(tss) else None
        if not ts:
            hard += 1
            penalty += HARD_CONFLICT_WEIGHT
            continue
        penalty += ts.penalty
        if len(gene.assignments) != len(ts.templates):
            missing_assignments = abs(len(ts.templates) - len(gene.assignments))
            hard += max(1, missing_assignments)
            penalty += HARD_CONFLICT_WEIGHT * max(1, missing_assignments)

        for a in gene.assignments:
            tmpl = ts.templates[a.template_id] if a.template_id < len(ts.templates) else None
            if not tmpl:
                hard += 1
                penalty += HARD_CONFLICT_WEIGHT
                continue
            if scorer:
                ml_score_total += scorer.score(task, tmpl, a.slot_id, a.classroom_id)
            profile_value, _ = profile_penalty(task.teacher_profile, a.slot_id)
            penalty += profile_value * len(tmpl.weeks_list)
            for wn in tmpl.weeks_list:
                key = (a.slot_id, wn)
                slot_week_usage[key].append((task.task_id, task.teacher_id, _task_class_group_ids(task), a.classroom_id))
                all_assigns.append(a)

    missing_task_ids = set(task_map) - scheduled_task_ids
    if missing_task_ids:
        hard += len(missing_task_ids)
        penalty += HARD_CONFLICT_WEIGHT * len(missing_task_ids)

    # 教师冲突
    for key, users in slot_week_usage.items():
        teachers = set()
        for tid, tch, cgs, rid in users:
            if tch in teachers:
                hard += 1
                penalty += HARD_CONFLICT_WEIGHT
            teachers.add(tch)

    # 班级冲突
    for key, users in slot_week_usage.items():
        cg_set = set()
        for tid, tch, cgs, rid in users:
            for cg in cgs:
                if cg in cg_set:
                    hard += 1
                    penalty += HARD_CONFLICT_WEIGHT
                cg_set.add(cg)

    # 教室冲突
    room_slot_week: dict[tuple[int, int, int], list] = defaultdict(list)
    for key, users in slot_week_usage.items():
        sid, wn = key
        for tid, tch, cgs, rid in users:
            room_slot_week[(rid, wn, sid)].append(tid)
    for key, users in room_slot_week.items():
        if len(users) > 1:
            hard += len(users) - 1
            penalty += HARD_CONFLICT_WEIGHT * (len(users) - 1)

    # 同一天重复课
    for gene in chromosome:
        day_usage = defaultdict(int)
        for a in gene.assignments:
            day, _ = slot_to_day_period(a.slot_id)
            day_usage[day] += 1
        for count in day_usage.values():
            if count > 1:
                penalty += SAME_DAY_WEIGHT

    penalty -= ML_SCORE_WEIGHT * ml_score_total

    return {
        "fitness": max(0, 10_000_000 - int(penalty)),
        "penalty": penalty,
        "hard_conflicts": hard,
        "assignments": len(all_assigns),
        "ml_score_total": ml_score_total,
        "missing_task_count": len(missing_task_ids),
        "duplicate_task_count": len(duplicate_task_ids),
    }


# ── 交叉（task-level uniform） ──────────────────────────


def crossover(
    p1: list[TaskGene], p2: list[TaskGene], rng: random.Random,
) -> list[TaskGene]:
    child = []
    p1_by_task = {gene.task_id: gene for gene in p1}
    p2_by_task = {gene.task_id: gene for gene in p2}
    for task_id in sorted(set(p1_by_task) | set(p2_by_task)):
        g1 = p1_by_task.get(task_id)
        g2 = p2_by_task.get(task_id)
        if g1 and g2:
            child.append(g1 if rng.random() < 0.5 else g2)
        elif g1:
            child.append(g1)
        elif g2:
            child.append(g2)
    return child


# ── 变异 ────────────────────────────────────────────────


def mutate(
    chromosome: list[TaskGene],
    tasks: list[AllocationTask],
    rate: float,
    rng: random.Random,
) -> list[TaskGene]:
    task_map = {t.task_id: t for t in tasks}
    result: list[TaskGene] = []

    for gene in chromosome:
        task = task_map.get(gene.task_id)
        if not task:
            result.append(gene)
            continue

        mg = gene

        # 模板集在个体初始化/交叉后保持稳定；变异只调整 slot/classroom
        new_assigns = []
        for a in mg.assignments:
            if rng.random() < rate:
                if not task.candidate_slot_ids or not task.candidate_room_ids:
                    new_assigns.append(a)
                    continue
                sid = rng.choice(task.candidate_slot_ids)
                rid = rng.choice(task.candidate_room_ids)
                new_assigns.append(TemplateAssignment(template_id=a.template_id, slot_id=sid, classroom_id=rid))
            else:
                new_assigns.append(a)
        mg = TaskGene(task_id=mg.task_id, template_set_id=mg.template_set_id, assignments=new_assigns)

        # swap 两个模板的 slot
        if rng.random() < rate * 0.3 and len(mg.assignments) >= 2:
            ai, aj = rng.sample(range(len(mg.assignments)), 2)
            assigns = list(mg.assignments)
            a1, a2 = assigns[ai], assigns[aj]
            assigns[ai] = TemplateAssignment(template_id=a1.template_id, slot_id=a2.slot_id, classroom_id=a1.classroom_id)
            assigns[aj] = TemplateAssignment(template_id=a2.template_id, slot_id=a1.slot_id, classroom_id=a2.classroom_id)
            mg = TaskGene(task_id=mg.task_id, template_set_id=mg.template_set_id, assignments=assigns)

        result.append(mg)

    return result


# ── 修复 ─────────────────────────────────────────────────


MAX_REPAIR_ATTEMPTS = 30


def repair(
    chromosome: list[TaskGene],
    tasks: list[AllocationTask],
    rng: random.Random,
    scorer: AssignmentScorer | None = None,
) -> list[TaskGene]:
    task_map = {t.task_id: t for t in tasks}

    for gi in range(len(chromosome)):
        gene = chromosome[gi]
        task = task_map.get(gene.task_id)
        if not task:
            continue
        tss = task.template_sets
        ts = tss[gene.template_set_id] if gene.template_set_id < len(tss) else None
        if not ts:
            continue

        new_assigns = list(gene.assignments)

        for ai, a in enumerate(gene.assignments):
            tmpl = ts.templates[a.template_id] if a.template_id < len(ts.templates) else None
            if not tmpl:
                continue

            current_teacher_class, current_room, current_total = _candidate_conflicts(
                chromosome, tasks, gi, ai, tmpl, a.slot_id, a.classroom_id
            )
            if current_total == 0:
                continue

            candidate_pairs = _repair_candidate_pairs(task, a.slot_id, a.classroom_id, current_teacher_class, current_room, rng)
            scored_candidates = []
            for sid, rid in candidate_pairs[:MAX_REPAIR_ATTEMPTS]:
                teacher_class_conflicts, room_conflicts, total_conflicts = _candidate_conflicts(
                    chromosome, tasks, gi, ai, tmpl, sid, rid
                )
                rule_penalty = _slot_room_penalty(sid, rid, tmpl, task, {}, {}, {})
                ml_score = scorer.score(task, tmpl, sid, rid) if scorer else 0.0
                scored_candidates.append((
                    total_conflicts,
                    teacher_class_conflicts,
                    room_conflicts,
                    rule_penalty,
                    -ml_score,
                    sid,
                    rid,
                ))

            if not scored_candidates:
                continue

            scored_candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
            best_total, _tc, _room, _rule, _ml, best_slot, best_room = scored_candidates[0]
            if best_total <= current_total:
                new_assigns[ai] = TemplateAssignment(template_id=a.template_id, slot_id=best_slot, classroom_id=best_room)

        chromosome[gi] = TaskGene(task_id=gene.task_id, template_set_id=gene.template_set_id, assignments=new_assigns)

    return chromosome


def _repair_candidate_pairs(
    task: AllocationTask,
    current_slot: int,
    current_room: int,
    teacher_class_conflicts: int,
    room_conflicts: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    if room_conflicts and not teacher_class_conflicts:
        pairs.extend((current_slot, rid) for rid in task.candidate_room_ids if rid != current_room)
    if teacher_class_conflicts:
        pairs.extend((sid, current_room) for sid in task.candidate_slot_ids if sid != current_slot)
    pairs.extend(
        (sid, rid)
        for sid in task.candidate_slot_ids
        for rid in task.candidate_room_ids
        if sid != current_slot or rid != current_room
    )
    rng.shuffle(pairs)
    seen: set[tuple[int, int]] = set()
    unique_pairs = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique_pairs.append(pair)
    return unique_pairs


def _candidate_conflicts(
    chromosome: list[TaskGene],
    tasks: list[AllocationTask],
    gene_index: int,
    assignment_index: int,
    tmpl,
    slot_id: int,
    classroom_id: int,
) -> tuple[int, int, int]:
    task_map = {t.task_id: t for t in tasks}
    task = task_map.get(chromosome[gene_index].task_id)
    if not task:
        return 0, 0, 0

    teacher_class_conflicts = 0
    room_conflicts = 0
    for gj, other_gene in enumerate(chromosome):
        other_task = task_map.get(other_gene.task_id)
        if not other_task:
            continue
        other_sets = other_task.template_sets
        other_ts = other_sets[other_gene.template_set_id] if other_gene.template_set_id < len(other_sets) else None
        if not other_ts:
            continue
        for ai, other_assignment in enumerate(other_gene.assignments):
            if gj == gene_index and ai == assignment_index:
                continue
            if other_assignment.slot_id != slot_id:
                continue
            other_tmpl = other_ts.templates[other_assignment.template_id] if other_assignment.template_id < len(other_ts.templates) else None
            if not other_tmpl or not weeks_overlap(tmpl.week_mask, other_tmpl.week_mask):
                continue
            if other_task.teacher_id == task.teacher_id:
                teacher_class_conflicts += 1
            if set(_task_class_group_ids(other_task)) & set(_task_class_group_ids(task)):
                teacher_class_conflicts += 1
            if other_assignment.classroom_id == classroom_id:
                room_conflicts += 1

    return teacher_class_conflicts, room_conflicts, teacher_class_conflicts + room_conflicts


# ── 进化主循环 ───────────────────────────────────────────


def evolve(
    tasks: list[AllocationTask],
    rng: random.Random,
    *,
    pop_size: int = 60,
    generations: int = 60,
    elite_size: int = 5,
    tournament_size: int = 4,
    mutation_rate: float = 0.15,
    scorer: AssignmentScorer | None = None,
) -> tuple[list[TaskGene], dict[str, Any]]:
    pop = init_population(tasks, pop_size, rng, scorer)

    for gen in range(1, generations + 1):
        scored = [{"ind": ind, "metrics": fitness(ind, tasks, scorer)} for ind in pop]
        scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)

        best = scored[0]
        if gen == 1 or gen == generations or gen % 10 == 0:
            m = best["metrics"]
            _log.info("Gen %3d: fitness=%s penalty=%s hard=%s", gen, m["fitness"], m["penalty"], m["hard_conflicts"])

        elite = max(1, min(elite_size, len(scored)))
        nxt = [item["ind"][:] for item in scored[:elite]]

        while len(nxt) < pop_size:
            a = _tournament(scored, tournament_size, rng)
            b = _tournament(scored, tournament_size, rng)
            child = crossover(a, b, rng)
            child = mutate(child, tasks, mutation_rate, rng)
            child = repair(child, tasks, rng, scorer)
            nxt.append(child)

        pop = nxt

    scored = [{"ind": ind, "metrics": fitness(ind, tasks, scorer)} for ind in pop]
    scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return scored[0]["ind"], scored[0]["metrics"]


def _tournament(scored: list, size: int, rng: random.Random) -> list[TaskGene]:
    selected = [scored[rng.randrange(len(scored))] for _ in range(size)]
    selected.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return selected[0]["ind"]
