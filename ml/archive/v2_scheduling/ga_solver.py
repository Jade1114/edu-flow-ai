"""GA solver over task-level candidate indexes."""

from __future__ import annotations

from dataclasses import dataclass
import random
import logging
import time

from collections import Counter, defaultdict

from ml.scheduling_v2.fitness import evaluate, expand_chromosome, fitness_key
from ml.scheduling_v2.models import ScheduleContext, SolvedScheme, TaskCandidate

_log = logging.getLogger("ga")
ResourceKey = tuple[str, int, int]


@dataclass(frozen=True)
class _CandidateStats:
    candidate: TaskCandidate | None
    resource_counts: Counter[ResourceKey]
    static_hard: int
    score: float
    profile_penalty: float
    template_signature: str
    slot_signature: tuple[tuple[int, int, int, int], ...]
    room_signature: tuple[int, ...]


@dataclass(frozen=True)
class _LocalTaskIndex:
    by_template: dict[str, list[int]]
    by_template_slot: dict[tuple[str, tuple[tuple[int, int, int, int], ...]], list[int]]
    by_template_room: dict[tuple[str, tuple[int, ...]], list[int]]


@dataclass(frozen=True)
class _CandidateIndex:
    stats_by_task: list[list[_CandidateStats]]
    invalid_stats_by_task: list[_CandidateStats]
    local_by_task: list[_LocalTaskIndex]
    profile_penalty_scale: float


@dataclass(frozen=True)
class _RepairStats:
    trials: int = 0
    applied: int = 0
    trial_ms: float = 0.0
    local_teacher_slot: int = 0
    local_class_slot: int = 0
    local_room_only: int = 0
    fallback: int = 0


@dataclass(frozen=True)
class _MutationStats:
    conflict_tasks: int = 0
    directed_applied: int = 0
    random_fallback: int = 0


@dataclass(frozen=True)
class _ChromosomeState:
    chromosome: tuple[int, ...]
    resource_counts: Counter[ResourceKey]
    duplicate_hard: int
    static_hard: int
    candidate_score: float
    profile_penalty: float
    profile_penalty_scale: float

    @property
    def hard_conflicts(self) -> int:
        return self.duplicate_hard + self.static_hard

    @property
    def quality_score(self) -> float:
        return self.candidate_score - self.profile_penalty * self.profile_penalty_scale

    @property
    def fitness_key(self) -> tuple[int, float]:
        return (self.hard_conflicts, -self.quality_score)


def solve(
    context: ScheduleContext,
    pools: list[list[TaskCandidate]],
    *,
    scheme_count: int,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    rng: random.Random,
    repair_max_tasks: int = 2,
    repair_candidate_limit: int = 12,
    greedy_init_scan_limit: int = 8,
    greedy_init_variants: int = 2,
    directed_mutation_scan_limit: int = 0,
    local_repair_enabled: bool = True,
    local_repair_candidate_limit: int = 12,
    local_mutation_enabled: bool = True,
    local_mutation_candidate_limit: int = 8,
) -> list[SolvedScheme]:
    if not pools:
        raise ValueError("排课失败：候选池为空")

    _log.info(
        "GA solver start: tasks=%s population=%s generations=%s elite=%s tournament=%s mutation=%.3f "
        "repair_max_tasks=%s repair_candidate_limit=%s greedy_init_scan_limit=%s "
        "greedy_init_variants=%s directed_mutation_scan_limit=%s local_repair=%s/%s local_mutation=%s/%s",
        len(pools),
        population_size,
        generations,
        elite_size,
        tournament_size,
        mutation_rate,
        repair_max_tasks,
        repair_candidate_limit,
        greedy_init_scan_limit,
        greedy_init_variants,
        directed_mutation_scan_limit,
        local_repair_enabled,
        local_repair_candidate_limit,
        local_mutation_enabled,
        local_mutation_candidate_limit,
    )
    candidate_index = _build_candidate_index(context, pools)
    population = _initial_population(
        pools,
        candidate_index,
        population_size,
        rng,
        greedy_init_scan_limit=greedy_init_scan_limit,
        greedy_init_variants=greedy_init_variants,
    )
    initial_evaluated = [(chromosome, evaluate(chromosome, context, pools)) for chromosome in population[: min(len(population), 8)]]
    initial_best = min((fit.hard_conflicts for _chromosome, fit in initial_evaluated), default=None)
    _log.info(
        "GA initial population built: population=%s greedy_variants=%s best_initial_conflicts=%s",
        len(population),
        min(len(population), 1 + max(0, greedy_init_variants)),
        initial_best,
    )
    archive: dict[tuple[int, ...], SolvedScheme] = {}
    repair_attempts = 0
    repair_improvements = 0
    best_seen = None
    log_every = max(1, generations // 10)

    for generation in range(max(1, generations)):
        generation_started_at = time.perf_counter()
        _log.info(
            "GA generation start: generation=%s/%s population=%s archive=%s/%s",
            generation + 1,
            generations,
            len(population),
            len(archive),
            scheme_count,
        )
        eval_started_at = time.perf_counter()
        evaluated = [(chromosome, evaluate(chromosome, context, pools)) for chromosome in population]
        eval_ms = (time.perf_counter() - eval_started_at) * 1000
        sort_started_at = time.perf_counter()
        evaluated.sort(key=lambda item: fitness_key(item[1]))
        sort_ms = (time.perf_counter() - sort_started_at) * 1000
        best_seen = evaluated[0][1] if evaluated else best_seen
        archive_started_at = time.perf_counter()
        _collect_archive(evaluated, context, pools, archive, scheme_count)
        archive_ms = (time.perf_counter() - archive_started_at) * 1000
        if generation == 0 or generation % log_every == 0:
            _log.info(
                "GA generation evaluated: generation=%s/%s best_conflicts=%s best_quality=%.4f archive=%s/%s repair=%s/%s "
                "ms={eval:%.1f,sort:%.1f,archive:%.1f}",
                generation + 1,
                generations,
                best_seen.hard_conflicts if best_seen else None,
                best_seen.quality_score if best_seen else 0.0,
                len(archive),
                scheme_count,
                repair_improvements,
                repair_attempts,
                eval_ms,
                sort_ms,
                archive_ms,
            )

        if len(archive) >= scheme_count and generation >= max(2, generations // 5):
            break

        reproduce_started_at = time.perf_counter()
        next_population = [chromosome for chromosome, _fit in evaluated[: max(1, elite_size)]]
        generation_repair_attempts = 0
        generation_repair_improvements = 0
        generation_repair_ms = 0.0
        generation_conflict_scan_ms = 0.0
        generation_directed_applied = 0
        generation_random_fallback = 0
        generation_conflict_tasks = 0
        last_reproduce_progress_at = reproduce_started_at
        while len(next_population) < population_size:
            child_number = len(next_population) + 1
            parent_a = _tournament(evaluated, tournament_size, rng)
            parent_b = _tournament(evaluated, tournament_size, rng)
            child = _crossover(parent_a, parent_b, rng)
            conflict_scan_started_at = time.perf_counter()
            child_state = _build_chromosome_state(child, candidate_index)
            pressure = _conflict_pressure_by_task(child_state, candidate_index)
            conflict_indexes = set(pressure)
            generation_conflict_scan_ms += (time.perf_counter() - conflict_scan_started_at) * 1000
            if directed_mutation_scan_limit > 0:
                child, mutation_stats = _directed_mutate(
                    child,
                    pools,
                    candidate_index,
                    mutation_rate,
                    rng,
                    scan_limit=directed_mutation_scan_limit,
                    state=child_state,
                    pressure=pressure,
                )
            else:
                if local_mutation_enabled:
                    child, mutation_stats = _local_mutate(
                        child_state,
                        pools,
                        candidate_index,
                        mutation_rate,
                        rng,
                        pressure=pressure,
                        candidate_limit=local_mutation_candidate_limit,
                    )
                else:
                    child = _mutate(child, pools, mutation_rate, rng, conflict_indexes=conflict_indexes)
                    mutation_stats = _MutationStats(
                        conflict_tasks=len(conflict_indexes),
                        directed_applied=0,
                        random_fallback=0,
                    )
            generation_directed_applied += mutation_stats.directed_applied
            generation_random_fallback += mutation_stats.random_fallback
            generation_conflict_tasks += mutation_stats.conflict_tasks
            repair_started_at = time.perf_counter()
            repaired_child, improved, repair_stats = _repair(
                child,
                pools,
                candidate_index,
                rng,
                max_tasks=repair_max_tasks,
                candidate_limit=repair_candidate_limit,
                local_enabled=local_repair_enabled,
                local_candidate_limit=local_repair_candidate_limit,
            )
            repair_elapsed_ms = (time.perf_counter() - repair_started_at) * 1000
            generation_repair_ms += repair_elapsed_ms
            generation_repair_attempts += 1
            repair_attempts += 1
            if improved:
                generation_repair_improvements += 1
                repair_improvements += 1
            if repair_elapsed_ms >= 2000:
                _log.info(
                    "GA repair slow: generation=%s/%s child=%s/%s conflict_tasks=%s improved=%s "
                    "repair_trials=%s repair_applied=%s local={teacher_slot:%s,class_slot:%s,room_only:%s,fallback:%s} "
                    "avg_trial_ms=%.3f elapsed_ms=%.1f",
                    generation + 1,
                    generations,
                    child_number,
                    population_size,
                    len(conflict_indexes),
                    improved,
                    repair_stats.trials,
                    repair_stats.applied,
                    repair_stats.local_teacher_slot,
                    repair_stats.local_class_slot,
                    repair_stats.local_room_only,
                    repair_stats.fallback,
                    repair_stats.trial_ms / max(1, repair_stats.trials),
                    repair_elapsed_ms,
                )
            child = repaired_child
            next_population.append(child)
            if (
                len(next_population) == population_size
                or len(next_population) % 25 == 0
                or (time.perf_counter() - last_reproduce_progress_at) >= 30
            ):
                last_reproduce_progress_at = time.perf_counter()
                _log.info(
                    "GA local mutation: generation=%s/%s conflict_tasks=%s local_applied=%s random_fallback=%s",
                    generation + 1,
                    generations,
                    generation_conflict_tasks,
                    generation_directed_applied,
                    generation_random_fallback,
                )
                _log.info(
                    "GA reproduce progress: generation=%s/%s next_population=%s/%s repair=%s/%s "
                    "local_applied=%s random_fallback=%s conflict_tasks=%s "
                    "last_repair_trials=%s last_repair_applied=%s last_local={teacher_slot:%s,class_slot:%s,room_only:%s,fallback:%s} "
                    "last_avg_trial_ms=%.3f "
                    "ms={conflict_scan:%.1f,repair:%.1f,reproduce_total:%.1f}",
                    generation + 1,
                    generations,
                    len(next_population),
                    population_size,
                    generation_repair_improvements,
                    generation_repair_attempts,
                    generation_directed_applied,
                    generation_random_fallback,
                    generation_conflict_tasks,
                    repair_stats.trials,
                    repair_stats.applied,
                    repair_stats.local_teacher_slot,
                    repair_stats.local_class_slot,
                    repair_stats.local_room_only,
                    repair_stats.fallback,
                    repair_stats.trial_ms / max(1, repair_stats.trials),
                    generation_conflict_scan_ms,
                    generation_repair_ms,
                    (time.perf_counter() - reproduce_started_at) * 1000,
                )
        population = next_population
        reproduce_ms = (time.perf_counter() - reproduce_started_at) * 1000
        _log.info(
            "GA generation done: generation=%s/%s best_conflicts=%s best_quality=%.4f archive=%s/%s "
            "repair=%s/%s local_applied=%s random_fallback=%s conflict_tasks=%s "
            "ms={eval:%.1f,sort:%.1f,archive:%.1f,reproduce:%.1f,total:%.1f}",
            generation + 1,
            generations,
            best_seen.hard_conflicts if best_seen else None,
            best_seen.quality_score if best_seen else 0.0,
            len(archive),
            scheme_count,
            generation_repair_improvements,
            generation_repair_attempts,
            generation_directed_applied,
            generation_random_fallback,
            generation_conflict_tasks,
            eval_ms,
            sort_ms,
            archive_ms,
            reproduce_ms,
            (time.perf_counter() - generation_started_at) * 1000,
        )

    evaluated = [(chromosome, evaluate(chromosome, context, pools)) for chromosome in population]
    evaluated.sort(key=lambda item: fitness_key(item[1]))
    _collect_archive(evaluated, context, pools, archive, scheme_count)
    best_seen = evaluated[0][1] if evaluated else best_seen
    _log.info(
        "GA finished: best_conflicts=%s best_quality=%.4f archive=%s/%s repair=%s/%s",
        best_seen.hard_conflicts if best_seen else None,
        best_seen.quality_score if best_seen else 0.0,
        len(archive),
        scheme_count,
        repair_improvements,
        repair_attempts,
    )

    solved = sorted(archive.values(), key=lambda scheme: fitness_key(scheme.fitness))
    if len(solved) < scheme_count:
        best = evaluated[0][1] if evaluated else None
        detail = best.conflict_summary if best else {}
        raise ValueError(f"排课失败：未找到足够无冲突方案，已找到 {len(solved)}/{scheme_count}，最佳冲突={detail}")
    return [
        SolvedScheme(
            chromosome=scheme.chromosome,
            fitness=scheme.fitness,
            assignments=scheme.assignments,
            scheme_index=index + 1,
        )
        for index, scheme in enumerate(solved[:scheme_count])
    ]


def _initial_population(
    pools: list[list[TaskCandidate]],
    candidate_index: _CandidateIndex,
    population_size: int,
    rng: random.Random,
    *,
    greedy_init_scan_limit: int,
    greedy_init_variants: int,
) -> list[tuple[int, ...]]:
    del candidate_index, greedy_init_scan_limit
    population: list[tuple[int, ...]] = []
    greedy = tuple(0 for _pool in pools)
    population.append(greedy)
    population.append(_greedy_chromosome(pools, rng, randomize=False))

    if any(len(pool) > 1 for pool in pools):
        population.append(tuple(min(1, len(pool) - 1) for pool in pools))

    grasp_count = max(0, min(greedy_init_variants, population_size - len(population)))
    for _variant in range(grasp_count):
        population.append(_greedy_chromosome(pools, rng, randomize=True))

    while len(population) < population_size:
        population.append(tuple(rng.randrange(len(pool)) for pool in pools))
    return population[:population_size]


def _global_greedy_chromosome(
    pools: list[list[TaskCandidate]],
    candidate_index: _CandidateIndex,
    rng: random.Random,
    *,
    scan_limit: int,
    randomize_order: bool,
    scan_offset: int = 0,
) -> tuple[int, ...]:
    genes = [-1 for _pool in pools]
    state = _build_chromosome_state(tuple(genes), candidate_index)
    order = _task_order_for_greedy(pools)
    if randomize_order:
        order = _shuffle_order_window(order, rng, window=max(4, min(32, len(order))))

    for task_index in order:
        best_state = None
        best_gene = 0
        for candidate_gene in _scan_candidate_indexes(pools[task_index], scan_limit=scan_limit, offset=scan_offset):
            trial = _replace_candidate_state(state, task_index, candidate_gene, candidate_index)
            if best_state is None or trial.fitness_key < best_state.fitness_key:
                best_state = trial
                best_gene = candidate_gene
        genes[task_index] = best_gene
        state = best_state if best_state is not None else _replace_candidate_state(state, task_index, 0, candidate_index)
    return tuple(max(0, gene) for gene in genes)


def _task_order_for_greedy(pools: list[list[TaskCandidate]]) -> list[int]:
    order = list(range(len(pools)))
    order.sort(key=lambda index: (
        len(pools[index]),
        -max((len(candidate.assignments) for candidate in pools[index]), default=0),
        index,
    ))
    return order


def _shuffle_order_window(order: list[int], rng: random.Random, *, window: int) -> list[int]:
    pending = list(order)
    shuffled: list[int] = []
    while pending:
        pick_at = rng.randrange(min(window, len(pending)))
        shuffled.append(pending.pop(pick_at))
    return shuffled


def _scan_candidate_indexes(pool: list[TaskCandidate], *, scan_limit: int, offset: int = 0) -> list[int]:
    if not pool:
        return []
    limit = max(1, min(scan_limit, len(pool)))
    indexes = list(range(limit))
    if offset > 0 and len(indexes) > 1:
        offset = offset % len(indexes)
        indexes = indexes[offset:] + indexes[:offset]
    return indexes


def _greedy_chromosome(
    pools: list[list[TaskCandidate]],
    rng: random.Random,
    *,
    randomize: bool,
) -> tuple[int, ...]:
    genes = [0 for _pool in pools]
    teacher_slots: dict[tuple[int, int], int] = defaultdict(int)
    class_slots: dict[tuple[int, int], int] = defaultdict(int)
    room_slots: dict[tuple[int, int], int] = defaultdict(int)

    order = list(range(len(pools)))
    order.sort(key=lambda index: (-max(len(candidate.assignments) for candidate in pools[index]), len(pools[index])))
    if randomize:
        window = max(4, min(32, len(order)))
        shuffled: list[int] = []
        pending = order[:]
        while pending:
            pick_at = rng.randrange(min(window, len(pending)))
            shuffled.append(pending.pop(pick_at))
        order = shuffled

    for task_index in order:
        pool = pools[task_index]
        candidate_indexes = list(range(len(pool)))
        if randomize and len(candidate_indexes) > 1:
            top = candidate_indexes[: min(24, len(candidate_indexes))]
            rng.shuffle(top)
            candidate_indexes = top + candidate_indexes[len(top):]

        best_index = min(
            candidate_indexes,
            key=lambda candidate_index: _incremental_cost(
                pool[candidate_index],
                teacher_slots,
                class_slots,
                room_slots,
            ),
        )
        genes[task_index] = best_index
        _occupy(pool[best_index], teacher_slots, class_slots, room_slots)
    return tuple(genes)


def _incremental_cost(
    candidate: TaskCandidate,
    teacher_slots: dict[tuple[int, int], int],
    class_slots: dict[tuple[int, int], int],
    room_slots: dict[tuple[int, int], int],
) -> tuple[int, float]:
    conflicts = 0
    for assignment in candidate.assignments:
        conflicts += teacher_slots[(assignment.teacher_id, assignment.time_slot_id)]
        for class_group_id in assignment.class_group_ids:
            conflicts += class_slots[(class_group_id, assignment.time_slot_id)]
        conflicts += room_slots[(assignment.classroom_id, assignment.time_slot_id)]
    return (conflicts, -candidate.score)


def _occupy(
    candidate: TaskCandidate,
    teacher_slots: dict[tuple[int, int], int],
    class_slots: dict[tuple[int, int], int],
    room_slots: dict[tuple[int, int], int],
) -> None:
    for assignment in candidate.assignments:
        teacher_slots[(assignment.teacher_id, assignment.time_slot_id)] += 1
        for class_group_id in assignment.class_group_ids:
            class_slots[(class_group_id, assignment.time_slot_id)] += 1
        room_slots[(assignment.classroom_id, assignment.time_slot_id)] += 1


def _collect_archive(
    evaluated,
    context: ScheduleContext,
    pools: list[list[TaskCandidate]],
    archive: dict[tuple[int, ...], SolvedScheme],
    scheme_count: int,
) -> None:
    for chromosome, result in evaluated:
        if result.hard_conflicts != 0:
            continue
        signature = _scheme_signature(chromosome, pools)
        if signature in archive:
            continue
        archive[signature] = SolvedScheme(
            chromosome=chromosome,
            fitness=result,
            assignments=expand_chromosome(chromosome, pools),
            scheme_index=len(archive) + 1,
        )
        if len(archive) >= scheme_count * 3:
            break


def _scheme_signature(chromosome: tuple[int, ...], pools: list[list[TaskCandidate]]) -> tuple[int, ...]:
    # The chromosome itself is enough to dedupe exact candidate combinations.
    return chromosome


def _tournament(evaluated, tournament_size: int, rng: random.Random) -> tuple[int, ...]:
    competitors = rng.sample(evaluated, k=min(tournament_size, len(evaluated)))
    competitors.sort(key=lambda item: fitness_key(item[1]))
    return competitors[0][0]


def _crossover(parent_a: tuple[int, ...], parent_b: tuple[int, ...], rng: random.Random) -> tuple[int, ...]:
    return tuple(a if rng.random() < 0.5 else b for a, b in zip(parent_a, parent_b))


def _mutate(
    chromosome: tuple[int, ...],
    pools: list[list[TaskCandidate]],
    mutation_rate: float,
    rng: random.Random,
    *,
    conflict_indexes: set[int] | None = None,
) -> tuple[int, ...]:
    genes = list(chromosome)
    conflict_indexes = conflict_indexes or set()
    for index, pool in enumerate(pools):
        if len(pool) <= 1:
            continue
        effective_rate = max(mutation_rate, 0.30) if index in conflict_indexes else mutation_rate
        if rng.random() < effective_rate:
            genes[index] = rng.randrange(len(pool))
    return tuple(genes)


def _local_mutate(
    state: _ChromosomeState,
    pools: list[list[TaskCandidate]],
    candidate_index: _CandidateIndex,
    mutation_rate: float,
    rng: random.Random,
    *,
    pressure: dict[int, Counter[str]],
    candidate_limit: int,
) -> tuple[tuple[int, ...], _MutationStats]:
    current = state
    conflict_tasks = set(pressure)
    local_applied = 0
    random_fallback = 0
    for task_index, pool in enumerate(pools):
        if len(pool) <= 1:
            continue
        effective_rate = max(mutation_rate, 0.30) if task_index in conflict_tasks else mutation_rate
        if rng.random() >= effective_rate:
            continue
        if task_index in conflict_tasks:
            replacement = _best_local_replacement(
                current,
                task_index,
                candidate_index,
                pressure[task_index],
                candidate_limit=candidate_limit,
            )
            if replacement is not None:
                current, _kind = replacement
                local_applied += 1
                continue
        gene = rng.randrange(len(pool))
        if gene != current.chromosome[task_index]:
            current = _replace_candidate_state(current, task_index, gene, candidate_index)
            random_fallback += 1
    return current.chromosome, _MutationStats(
        conflict_tasks=len(conflict_tasks),
        directed_applied=local_applied,
        random_fallback=random_fallback,
    )


def _directed_mutate(
    chromosome: tuple[int, ...],
    pools: list[list[TaskCandidate]],
    candidate_index: _CandidateIndex,
    mutation_rate: float,
    rng: random.Random,
    *,
    scan_limit: int,
    state: _ChromosomeState | None = None,
    pressure: dict[int, Counter[str]] | None = None,
) -> tuple[tuple[int, ...], _MutationStats]:
    current = state or _build_chromosome_state(chromosome, candidate_index)
    pressure = pressure if pressure is not None else _conflict_pressure_by_task(current, candidate_index)
    conflict_tasks = set(pressure)
    directed_applied = 0
    random_fallback = 0

    for task_index, pool in enumerate(pools):
        if len(pool) <= 1:
            continue
        effective_rate = max(mutation_rate, 0.30) if task_index in conflict_tasks else mutation_rate
        if rng.random() >= effective_rate:
            continue

        if task_index in conflict_tasks:
            directed = _best_directed_replacement(
                current,
                task_index,
                pools,
                candidate_index,
                pressure[task_index],
                scan_limit=scan_limit,
            )
            if directed is not None:
                current = directed
                directed_applied += 1
                continue

        gene = rng.randrange(len(pool))
        if gene != current.chromosome[task_index]:
            current = _replace_candidate_state(current, task_index, gene, candidate_index)
            random_fallback += 1

    return current.chromosome, _MutationStats(
        conflict_tasks=len(conflict_tasks),
        directed_applied=directed_applied,
        random_fallback=random_fallback,
    )


def _best_directed_replacement(
    state: _ChromosomeState,
    task_index: int,
    pools: list[list[TaskCandidate]],
    candidate_index: _CandidateIndex,
    conflict_pressure: Counter[str],
    *,
    scan_limit: int,
) -> _ChromosomeState | None:
    pool = pools[task_index]
    current_gene = state.chromosome[task_index]
    current_stats = _stats_for_gene(candidate_index, task_index, current_gene)
    ordered_indexes = _directed_candidate_indexes(
        pool,
        current_stats,
        conflict_pressure,
        scan_limit=scan_limit,
    )
    best = state
    for candidate_gene in ordered_indexes:
        if candidate_gene == current_gene:
            continue
        trial = _replace_candidate_state(state, task_index, candidate_gene, candidate_index)
        if trial.fitness_key < best.fitness_key:
            best = trial
    return best if best is not state else None


def _directed_candidate_indexes(
    pool: list[TaskCandidate],
    current_stats: _CandidateStats,
    conflict_pressure: Counter[str],
    *,
    scan_limit: int,
) -> list[int]:
    indexes = _scan_candidate_indexes(pool, scan_limit=scan_limit)
    if not indexes:
        return []
    current_rooms, current_slots = _candidate_room_slot_sets(current_stats)
    prefer_room_change = conflict_pressure.get("room", 0) > 0
    prefer_slot_change = conflict_pressure.get("teacher", 0) > 0 or conflict_pressure.get("class", 0) > 0

    def priority(candidate_index_value: int) -> tuple[int, int]:
        candidate = pool[candidate_index_value]
        rooms = {assignment.classroom_id for assignment in candidate.assignments}
        slots = {assignment.time_slot_id for assignment in candidate.assignments}
        room_changed = rooms != current_rooms
        slot_changed = slots != current_slots
        matched = 0
        if prefer_room_change and room_changed:
            matched -= 1
        if prefer_slot_change and slot_changed:
            matched -= 1
        return (matched, candidate_index_value)

    indexes.sort(key=priority)
    return indexes


def _candidate_room_slot_sets(stats: _CandidateStats) -> tuple[set[int], set[int]]:
    if stats.candidate is None:
        return set(), set()
    return (
        {assignment.classroom_id for assignment in stats.candidate.assignments},
        {assignment.time_slot_id for assignment in stats.candidate.assignments},
    )


def _best_local_replacement(
    state: _ChromosomeState,
    task_index: int,
    candidate_index: _CandidateIndex,
    conflict_pressure: Counter[str],
    *,
    candidate_limit: int,
) -> tuple[_ChromosomeState, str] | None:
    best_state = state
    best_kind = ""
    for candidate_gene, kind in _local_replacement_candidates(
        candidate_index,
        task_index,
        state.chromosome[task_index],
        conflict_pressure,
        limit=candidate_limit,
    ):
        if candidate_gene == state.chromosome[task_index]:
            continue
        trial = _replace_candidate_state(state, task_index, candidate_gene, candidate_index)
        if trial.fitness_key < best_state.fitness_key:
            best_state = trial
            best_kind = kind
    return (best_state, best_kind) if best_state is not state else None


def _local_replacement_candidates(
    candidate_index: _CandidateIndex,
    task_index: int,
    current_gene: int,
    conflict_pressure: Counter[str],
    *,
    limit: int,
) -> list[tuple[int, str]]:
    if limit <= 0 or task_index < 0 or task_index >= len(candidate_index.stats_by_task):
        return []
    stats_by_candidate = candidate_index.stats_by_task[task_index]
    if current_gene < 0 or current_gene >= len(stats_by_candidate):
        return []
    current = stats_by_candidate[current_gene]
    local_index = candidate_index.local_by_task[task_index]
    ordered_sources: list[tuple[list[int], str]] = []
    if conflict_pressure.get("teacher", 0) > 0:
        ordered_sources.append((local_index.by_template.get(current.template_signature, []), "teacher_slot"))
    if conflict_pressure.get("class", 0) > 0:
        ordered_sources.append((local_index.by_template.get(current.template_signature, []), "class_slot"))
    if conflict_pressure.get("room", 0) > 0:
        ordered_sources.append((local_index.by_template_slot.get((current.template_signature, current.slot_signature), []), "room_only"))
        ordered_sources.append((local_index.by_template.get(current.template_signature, []), "room_any"))

    seen: set[int] = set()
    result: list[tuple[int, str]] = []
    for indexes, kind in ordered_sources:
        for candidate_gene in indexes:
            if candidate_gene == current_gene or candidate_gene in seen:
                continue
            candidate = stats_by_candidate[candidate_gene]
            if kind in {"teacher_slot", "class_slot"} and candidate.slot_signature == current.slot_signature:
                continue
            if kind == "room_only" and candidate.room_signature == current.room_signature:
                continue
            if kind == "room_any" and candidate.room_signature == current.room_signature:
                continue
            seen.add(candidate_gene)
            result.append((candidate_gene, kind))
            if len(result) >= limit:
                return result
    return result


def _build_candidate_index(
    context: ScheduleContext,
    pools: list[list[TaskCandidate]],
) -> _CandidateIndex:
    stats_by_task: list[list[_CandidateStats]] = []
    invalid_stats_by_task: list[_CandidateStats] = []
    local_by_task: list[_LocalTaskIndex] = []
    for task, pool in zip(context.tasks, pools):
        task_stats = [
            _candidate_stats(task, candidate, context.allowed_time_slot_ids)
            for candidate in pool
        ]
        stats_by_task.append(task_stats)
        local_by_task.append(_build_local_task_index(task_stats))
        invalid_stats_by_task.append(_invalid_candidate_stats(task))
    slot_replacements = 0
    room_replacements = 0
    for local_index in local_by_task:
        slot_replacements += sum(max(0, len(indexes) - 1) for indexes in local_index.by_template.values())
        room_replacements += sum(max(0, len(indexes) - 1) for indexes in local_index.by_template_slot.values())
    _log.info(
        "GA local index built: tasks=%s slot_replacements=%s room_replacements=%s",
        len(stats_by_task),
        slot_replacements,
        room_replacements,
    )
    return _CandidateIndex(
        stats_by_task=stats_by_task,
        invalid_stats_by_task=invalid_stats_by_task,
        local_by_task=local_by_task,
        profile_penalty_scale=float(context.scoring_config.get("profile_penalty_scale", 0.001)),
    )


def _candidate_stats(
    task,
    candidate: TaskCandidate,
    allowed_time_slot_ids: frozenset[int],
) -> _CandidateStats:
    resource_counts: Counter[ResourceKey] = Counter()
    static_hard = 0
    if len(candidate.assignments) * 2 != task.total_hours:
        static_hard += 1
    for assignment in candidate.assignments:
        if assignment.time_slot_id not in allowed_time_slot_ids:
            static_hard += 1
        resource_counts[("teacher", assignment.teacher_id, assignment.time_slot_id)] += 1
        for class_group_id in assignment.class_group_ids:
            resource_counts[("class", class_group_id, assignment.time_slot_id)] += 1
        resource_counts[("room", assignment.classroom_id, assignment.time_slot_id)] += 1
    return _CandidateStats(
        candidate=candidate,
        resource_counts=resource_counts,
        static_hard=static_hard,
        score=candidate.score,
        profile_penalty=candidate.teacher_profile_penalty,
        template_signature=candidate.template_signature,
        slot_signature=_slot_signature(candidate),
        room_signature=_room_signature(candidate),
    )


def _invalid_candidate_stats(task) -> _CandidateStats:
    static_hard = 1
    if task.total_hours != 0:
        static_hard += 1
    return _CandidateStats(
        candidate=None,
        resource_counts=Counter(),
        static_hard=static_hard,
        score=0.0,
        profile_penalty=0.0,
        template_signature="",
        slot_signature=(),
        room_signature=(),
    )


def _build_local_task_index(stats_by_candidate: list[_CandidateStats]) -> _LocalTaskIndex:
    by_template: dict[str, list[int]] = defaultdict(list)
    by_template_slot: dict[tuple[str, tuple[tuple[int, int, int, int], ...]], list[int]] = defaultdict(list)
    by_template_room: dict[tuple[str, tuple[int, ...]], list[int]] = defaultdict(list)
    for index, stats in enumerate(stats_by_candidate):
        by_template[stats.template_signature].append(index)
        by_template_slot[(stats.template_signature, stats.slot_signature)].append(index)
        by_template_room[(stats.template_signature, stats.room_signature)].append(index)
    sort_key = lambda candidate_index: (-stats_by_candidate[candidate_index].score, candidate_index)
    return _LocalTaskIndex(
        by_template={key: sorted(indexes, key=sort_key) for key, indexes in by_template.items()},
        by_template_slot={key: sorted(indexes, key=sort_key) for key, indexes in by_template_slot.items()},
        by_template_room={key: sorted(indexes, key=sort_key) for key, indexes in by_template_room.items()},
    )


def _slot_signature(candidate: TaskCandidate) -> tuple[tuple[int, int, int, int], ...]:
    return tuple(
        sorted(
            (assignment.week_number, assignment.day_of_week, assignment.period_index, assignment.time_slot_id)
            for assignment in candidate.assignments
        )
    )


def _room_signature(candidate: TaskCandidate) -> tuple[int, ...]:
    return tuple(
        assignment.classroom_id
        for assignment in sorted(
            candidate.assignments,
            key=lambda assignment: (assignment.week_number, assignment.day_of_week, assignment.period_index, assignment.time_slot_id),
        )
    )


def _build_chromosome_state(
    chromosome: tuple[int, ...],
    candidate_index: _CandidateIndex,
) -> _ChromosomeState:
    resource_counts: Counter[ResourceKey] = Counter()
    static_hard = 0
    candidate_score = 0.0
    profile_penalty = 0.0
    for task_index in range(len(candidate_index.stats_by_task)):
        gene = chromosome[task_index] if task_index < len(chromosome) else -1
        stats = _stats_for_gene(candidate_index, task_index, gene)
        resource_counts.update(stats.resource_counts)
        static_hard += stats.static_hard
        candidate_score += stats.score
        profile_penalty += stats.profile_penalty
    return _ChromosomeState(
        chromosome=chromosome,
        resource_counts=resource_counts,
        duplicate_hard=_duplicate_hard(resource_counts),
        static_hard=static_hard,
        candidate_score=candidate_score,
        profile_penalty=profile_penalty,
        profile_penalty_scale=candidate_index.profile_penalty_scale,
    )


def _replace_candidate_state(
    state: _ChromosomeState,
    task_index: int,
    new_gene: int,
    candidate_index: _CandidateIndex,
) -> _ChromosomeState:
    old_gene = state.chromosome[task_index] if task_index < len(state.chromosome) else -1
    old_stats = _stats_for_gene(candidate_index, task_index, old_gene)
    new_stats = _stats_for_gene(candidate_index, task_index, new_gene)
    affected_keys = set(old_stats.resource_counts) | set(new_stats.resource_counts)

    resource_counts = state.resource_counts.copy()
    old_duplicate = sum(_duplicate_count(resource_counts.get(key, 0)) for key in affected_keys)
    for key, count in old_stats.resource_counts.items():
        resource_counts[key] -= count
        if resource_counts[key] <= 0:
            del resource_counts[key]
    resource_counts.update(new_stats.resource_counts)
    new_duplicate = sum(_duplicate_count(resource_counts.get(key, 0)) for key in affected_keys)

    genes = list(state.chromosome)
    genes[task_index] = new_gene
    return _ChromosomeState(
        chromosome=tuple(genes),
        resource_counts=resource_counts,
        duplicate_hard=state.duplicate_hard + new_duplicate - old_duplicate,
        static_hard=state.static_hard - old_stats.static_hard + new_stats.static_hard,
        candidate_score=state.candidate_score - old_stats.score + new_stats.score,
        profile_penalty=state.profile_penalty - old_stats.profile_penalty + new_stats.profile_penalty,
        profile_penalty_scale=state.profile_penalty_scale,
    )


def _stats_for_gene(candidate_index: _CandidateIndex, task_index: int, gene: int) -> _CandidateStats:
    if task_index < 0 or task_index >= len(candidate_index.stats_by_task):
        return _CandidateStats(None, Counter(), 1, 0.0, 0.0, "", (), ())
    if gene < 0 or gene >= len(candidate_index.stats_by_task[task_index]):
        return candidate_index.invalid_stats_by_task[task_index]
    return candidate_index.stats_by_task[task_index][gene]


def _duplicate_hard(resource_counts: Counter[ResourceKey]) -> int:
    return sum(_duplicate_count(count) for count in resource_counts.values())


def _duplicate_count(count: int) -> int:
    return max(0, count - 1)


def _ranked_conflicted_task_indexes(
    state: _ChromosomeState,
    candidate_index: _CandidateIndex,
) -> list[int]:
    pressure: dict[int, int] = defaultdict(int)
    overbooked = {
        key: count
        for key, count in state.resource_counts.items()
        if count > 1
    }
    for task_index in range(len(candidate_index.stats_by_task)):
        gene = state.chromosome[task_index] if task_index < len(state.chromosome) else -1
        stats = _stats_for_gene(candidate_index, task_index, gene)
        if stats.static_hard:
            pressure[task_index] += stats.static_hard * 1000
        for key, count in stats.resource_counts.items():
            total = overbooked.get(key, 0)
            if total > 1:
                pressure[task_index] += count * (total - 1)
    return [
        task_index
        for task_index, _score in sorted(pressure.items(), key=lambda item: (-item[1], item[0]))
    ]


def _conflict_pressure_by_task(
    state: _ChromosomeState,
    candidate_index: _CandidateIndex,
) -> dict[int, Counter[str]]:
    result: dict[int, Counter[str]] = defaultdict(Counter)
    overbooked = {
        key: count
        for key, count in state.resource_counts.items()
        if count > 1
    }
    for task_index in range(len(candidate_index.stats_by_task)):
        gene = state.chromosome[task_index] if task_index < len(state.chromosome) else -1
        stats = _stats_for_gene(candidate_index, task_index, gene)
        if stats.static_hard:
            result[task_index]["static"] += stats.static_hard
        for key, count in stats.resource_counts.items():
            total = overbooked.get(key, 0)
            if total > 1:
                result[task_index][key[0]] += count * (total - 1)
    return dict(result)


def _repair(
    chromosome: tuple[int, ...],
    pools: list[list[TaskCandidate]],
    stats_index: _CandidateIndex,
    rng: random.Random,
    *,
    max_tasks: int,
    candidate_limit: int,
    local_enabled: bool = True,
    local_candidate_limit: int = 12,
) -> tuple[tuple[int, ...], bool, _RepairStats]:
    if max_tasks <= 0 or candidate_limit <= 0:
        return chromosome, False, _RepairStats()
    current = _build_chromosome_state(chromosome, stats_index)
    if current.hard_conflicts == 0:
        return chromosome, False, _RepairStats()

    conflict_indexes = _ranked_conflicted_task_indexes(current, stats_index)
    if not conflict_indexes:
        return chromosome, False, _RepairStats()
    improved_any = False
    trials = 0
    applied = 0
    trial_ms = 0.0
    local_teacher_slot = 0
    local_class_slot = 0
    local_room_only = 0
    fallback = 0

    for task_index in conflict_indexes[:max_tasks]:
        pool = pools[task_index]
        if len(pool) <= 1:
            continue
        pressure = _conflict_pressure_by_task(current, stats_index).get(task_index, Counter())
        if local_enabled:
            local_replacement = _best_local_replacement(
                current,
                task_index,
                stats_index,
                pressure,
                candidate_limit=local_candidate_limit,
            )
            if local_replacement is not None:
                current, kind = local_replacement
                improved_any = True
                applied += 1
                if kind == "teacher_slot":
                    local_teacher_slot += 1
                elif kind == "class_slot":
                    local_class_slot += 1
                elif kind in {"room_only", "room_any"}:
                    local_room_only += 1
                if current.hard_conflicts == 0:
                    break
                continue
        for candidate_gene in _repair_candidate_indexes(pool, rng, limit=candidate_limit):
            if candidate_gene == current.chromosome[task_index]:
                continue
            fallback += 1
            trial_started_at = time.perf_counter()
            trial = _replace_candidate_state(current, task_index, candidate_gene, stats_index)
            trial_ms += (time.perf_counter() - trial_started_at) * 1000
            trials += 1
            if trial.fitness_key < current.fitness_key:
                current = trial
                improved_any = True
                applied += 1
                if current.hard_conflicts == 0:
                    break
        if current.hard_conflicts == 0:
            break
    return current.chromosome, improved_any, _RepairStats(
        trials=trials,
        applied=applied,
        trial_ms=trial_ms,
        local_teacher_slot=local_teacher_slot,
        local_class_slot=local_class_slot,
        local_room_only=local_room_only,
        fallback=fallback,
    )


def _repair_candidate_indexes(pool: list[TaskCandidate], rng: random.Random, *, limit: int) -> list[int]:
    del rng
    indexes = list(range(min(limit, len(pool))))
    seen: set[int] = set()
    result: list[int] = []
    for index in indexes:
        if index not in seen and index < len(pool):
            seen.add(index)
            result.append(index)
            if len(result) >= limit:
                break
    return result


def _conflicted_task_indexes(
    chromosome: tuple[int, ...],
    pools: list[list[TaskCandidate]],
) -> set[int]:
    resource_usage: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    conflicted: set[int] = set()
    for task_index, (gene, pool) in enumerate(zip(chromosome, pools)):
        if gene < 0 or gene >= len(pool):
            conflicted.add(task_index)
            continue
        candidate = pool[gene]
        for assignment in candidate.assignments:
            resource_usage[("teacher", assignment.teacher_id, assignment.time_slot_id)].append(task_index)
            for class_group_id in assignment.class_group_ids:
                resource_usage[("class", class_group_id, assignment.time_slot_id)].append(task_index)
            resource_usage[("room", assignment.classroom_id, assignment.time_slot_id)].append(task_index)

    for task_indexes in resource_usage.values():
        if len(task_indexes) > 1:
            conflicted.update(task_indexes)
    return conflicted
