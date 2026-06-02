"""Select globally compatible V3 task plans with a genetic algorithm.

This is the third V3 step:
task_plans.jsonl -> schemes.jsonl + ga_summary.json.

The chromosome is intentionally compact: each gene selects one prebuilt local
plan for the corresponding teaching task. This layer never creates new
resources and never edits plan templates.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SCHEME_COUNT = 3
DEFAULT_POPULATION_SIZE = 120
DEFAULT_GENERATIONS = 200
DEFAULT_ELITE_SIZE = 8
DEFAULT_TOURNAMENT_SIZE = 4
DEFAULT_MUTATION_RATE = 0.12
DEFAULT_REPAIR_TOP_K = 12
DEFAULT_REPAIR_MAX_TASKS = 6
DEFAULT_SEED = 42

ResourceKey = tuple[str, int, int, int, int]
ClassDayKey = tuple[int, int, int]
ClassCourseDayKey = tuple[int, str, int, int]
TaskDayKey = tuple[int, int, int]


@dataclass(frozen=True)
class PlanOption:
    task_index: int
    plan_index: int
    plan_id: str
    teaching_task_id: int
    teacher_id: int
    class_group_ids: tuple[int, ...]
    course_name: str
    assignments: tuple[dict[str, Any], ...]
    resource_counts: Counter[ResourceKey]
    teacher_slot_keys: tuple[int, ...]
    class_slot_keys: tuple[int, ...]
    room_slot_keys: tuple[int, ...]
    class_day_counts: Counter[ClassDayKey]
    class_course_day_counts: Counter[ClassCourseDayKey]
    task_day_counts: Counter[TaskDayKey]
    hard_static: int
    placement_score: float
    stability_score: float
    quality_score: float


@dataclass(frozen=True)
class TaskPlans:
    row: dict[str, Any]
    options: tuple[PlanOption, ...]


@dataclass(frozen=True)
class Fitness:
    hard_conflicts: int
    quality_score: float
    beauty_penalty: float
    conflict_summary: dict[str, int]
    assignment_count: int

    @property
    def key(self) -> tuple[int, float, float]:
        return (self.hard_conflicts, -self.quality_score, self.beauty_penalty)


@dataclass(frozen=True)
class Evaluated:
    chromosome: tuple[int, ...]
    fitness: Fitness


def select_global_plans_jsonl(
    task_plans_path: str | Path,
    *,
    scheme_count: int = DEFAULT_SCHEME_COUNT,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
    elite_size: int = DEFAULT_ELITE_SIZE,
    tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    repair_top_k: int = DEFAULT_REPAIR_TOP_K,
    repair_max_tasks: int = DEFAULT_REPAIR_MAX_TASKS,
    seed: int = DEFAULT_SEED,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    source_path = Path(task_plans_path)
    tasks = load_task_plans(source_path)
    if not tasks:
        raise ValueError("task_plans.jsonl has no schedulable task plans")

    started = time.perf_counter()
    rng = random.Random(seed)
    scheme_count = max(1, min(int(scheme_count), 20))
    population_size = max(2, int(population_size))
    generations = max(1, int(generations))
    elite_size = max(1, min(int(elite_size), population_size))
    tournament_size = max(2, min(int(tournament_size), population_size))
    mutation_rate = max(0.0, min(float(mutation_rate), 1.0))
    repair_top_k = max(0, min(int(repair_top_k), population_size))
    repair_max_tasks = max(0, int(repair_max_tasks))

    population = _initial_population(tasks, population_size, rng)
    archive: dict[tuple[int, ...], Evaluated] = {}
    best_conflicts_per_generation: list[int] = []

    for _generation in range(generations):
        evaluated = [_evaluate(chromosome, tasks) for chromosome in population]
        evaluated.sort(key=lambda item: item.fitness.key)
        if evaluated:
            best_conflicts_per_generation.append(evaluated[0].fitness.hard_conflicts)
        _collect_archive(archive, evaluated, scheme_count)

        repaired = [_repair(item.chromosome, tasks, max_tasks=repair_max_tasks) for item in evaluated[:repair_top_k]]
        repaired_eval = [_evaluate(chromosome, tasks) for chromosome in repaired]
        repaired_eval.sort(key=lambda item: item.fitness.key)
        _collect_archive(archive, repaired_eval, scheme_count)

        ranked = sorted({item.chromosome: item for item in evaluated + repaired_eval}.values(), key=lambda item: item.fitness.key)
        next_population = [item.chromosome for item in ranked[:elite_size]]
        while len(next_population) < population_size:
            parent_a = _tournament(ranked, tournament_size, rng).chromosome
            parent_b = _tournament(ranked, tournament_size, rng).chromosome
            child = _crossover(parent_a, parent_b, rng)
            child_fit = _evaluate(child, tasks)
            child = _mutate(child, tasks, mutation_rate, rng, _conflicted_task_indexes(child_fit, child, tasks))
            next_population.append(child)
        population = next_population

    final_evaluated = [_evaluate(chromosome, tasks) for chromosome in population]
    final_evaluated.sort(key=lambda item: item.fitness.key)
    _collect_archive(archive, final_evaluated, scheme_count)
    schemes = sorted(archive.values(), key=lambda item: item.fitness.key)[:scheme_count]
    if not schemes and final_evaluated:
        schemes = final_evaluated[:scheme_count]

    out_dir = Path(output_dir) if output_dir else source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    schemes_path = out_dir / "schemes.jsonl"
    summary_path = out_dir / "ga_summary.json"

    scheme_rows = [_scheme_to_json(index, evaluated, tasks) for index, evaluated in enumerate(schemes, start=1)]
    schemes_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in scheme_rows),
        encoding="utf-8",
    )

    runtime_ms = round((time.perf_counter() - started) * 1000, 2)
    summary = {
        "architecture": "v3_global_plan_selector_ga",
        "source_path": str(source_path),
        "output_path": str(schemes_path),
        "summary_path": str(summary_path),
        "task_count": len(tasks),
        "scheme_count": len(scheme_rows),
        "population_size": population_size,
        "generations": generations,
        "elite_size": elite_size,
        "tournament_size": tournament_size,
        "mutation_rate": mutation_rate,
        "repair_top_k": repair_top_k,
        "repair_max_tasks": repair_max_tasks,
        "seed": seed,
        "best_conflicts_per_generation": best_conflicts_per_generation,
        "schemes": [
            {
                "scheme_index": row["scheme_index"],
                "hard_conflicts": row["hard_conflicts"],
                "quality_score": row["quality_score"],
                "beauty_penalty": row["beauty_penalty"],
                "conflict_summary": row["conflict_summary"],
                "assignment_count": len(row["items"]),
            }
            for row in scheme_rows
        ],
        "runtime_ms": runtime_ms,
        "generated_at": _now_iso(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


def load_task_plans(path: str | Path) -> list[TaskPlans]:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"task plans file not found: {source_path}")
    tasks: list[TaskPlans] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for task_index, line in enumerate(handle):
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            options = tuple(_plan_option(task_index, row, plan_index, plan) for plan_index, plan in enumerate(row.get("plans") or []))
            if options:
                tasks.append(TaskPlans(row=row, options=options))
    return tasks


def _plan_option(task_index: int, row: dict[str, Any], plan_index: int, plan: dict[str, Any]) -> PlanOption:
    task = row.get("task") or {}
    input_data = row.get("input") or {}
    teaching_task_id = int(row.get("teaching_task_id") or 0)
    teacher_id = int(task.get("teacher_id") or 0)
    class_group_ids = tuple(int(value) for value in task.get("class_group_ids") or [] if int(value) > 0)
    course_name = str(input_data.get("course_name") or "")
    total_sessions = int(task.get("total_sessions") or 0)

    assignments: list[dict[str, Any]] = []
    resource_counts: Counter[ResourceKey] = Counter()
    teacher_slot_keys: list[int] = []
    class_slot_keys: list[int] = []
    room_slot_keys: list[int] = []
    class_day_counts: Counter[ClassDayKey] = Counter()
    class_course_day_counts: Counter[ClassCourseDayKey] = Counter()
    task_day_counts: Counter[TaskDayKey] = Counter()

    for segment in plan.get("segments") or []:
        resource = segment.get("resource") or {}
        slot = resource.get("slot") or {}
        classroom = resource.get("classroom") or {}
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        room_id = int(classroom.get("id") or 0)
        for week in segment.get("weeks") or []:
            week_number = int(week)
            assignment = {
                "teaching_task_id": teaching_task_id,
                "teacher_id": teacher_id,
                "class_group_ids": list(class_group_ids),
                "classroom_id": room_id,
                "time_slot_id": None,
                "week_number": week_number,
                "day_of_week": day,
                "period_index": period,
                "classroom_name": classroom.get("name") or "",
                "placement_score": float(resource.get("score") or 0.0),
                "selected_plan_id": plan.get("plan_id") or f"{teaching_task_id}_p{plan_index + 1:03d}",
                "template_id": segment.get("template_id") or "",
            }
            assignments.append(assignment)
            if teacher_id > 0:
                resource_counts[("teacher", teacher_id, week_number, day, period)] += 1
                teacher_slot_keys.append(_packed_slot_key(teacher_id, week_number, day, period))
            if room_id > 0:
                resource_counts[("room", room_id, week_number, day, period)] += 1
                room_slot_keys.append(_packed_slot_key(room_id, week_number, day, period))
            task_day_counts[(teaching_task_id, week_number, day)] += 1
            for class_group_id in class_group_ids:
                resource_counts[("class", class_group_id, week_number, day, period)] += 1
                class_slot_keys.append(_packed_slot_key(class_group_id, week_number, day, period))
                class_day_counts[(class_group_id, week_number, day)] += 1
                class_course_day_counts[(class_group_id, course_name, week_number, day)] += 1

    hard_static = 0 if len(assignments) == total_sessions else 1
    placement_score = float(plan.get("score") or 0.0)
    segment_count = len(plan.get("segments") or [])
    stability_score = 1.0 / max(1, segment_count)
    quality_score = placement_score * total_sessions + stability_score
    return PlanOption(
        task_index=task_index,
        plan_index=plan_index,
        plan_id=str(plan.get("plan_id") or f"{teaching_task_id}_p{plan_index + 1:03d}"),
        teaching_task_id=teaching_task_id,
        teacher_id=teacher_id,
        class_group_ids=class_group_ids,
        course_name=course_name,
        assignments=tuple(assignments),
        resource_counts=resource_counts,
        teacher_slot_keys=tuple(teacher_slot_keys),
        class_slot_keys=tuple(class_slot_keys),
        room_slot_keys=tuple(room_slot_keys),
        class_day_counts=class_day_counts,
        class_course_day_counts=class_course_day_counts,
        task_day_counts=task_day_counts,
        hard_static=hard_static,
        placement_score=placement_score,
        stability_score=stability_score,
        quality_score=quality_score,
    )


def _initial_population(tasks: list[TaskPlans], population_size: int, rng: random.Random) -> list[tuple[int, ...]]:
    population: list[tuple[int, ...]] = [tuple(0 for _ in tasks)]
    greedy_variants = min(4, max(1, population_size // 12))
    for variant in range(greedy_variants):
        population.append(_greedy_chromosome(tasks, start_offset=variant))
    while len(population) < population_size:
        chromosome = []
        for task in tasks:
            pool_size = len(task.options)
            preferred = min(pool_size, 5)
            chromosome.append(rng.randrange(preferred if rng.random() < 0.85 else pool_size))
        population.append(tuple(chromosome))
    return _dedupe_population(population, tasks, population_size, rng)


def _greedy_chromosome(tasks: list[TaskPlans], *, start_offset: int) -> tuple[int, ...]:
    selected: list[int] = []
    resource_counts: Counter[ResourceKey] = Counter()
    for task_position in range(len(tasks)):
        task = tasks[(task_position + start_offset) % len(tasks)]
        best_index = 0
        best_key: tuple[int, float] | None = None
        for option in task.options:
            delta = _hard_delta(resource_counts, option.resource_counts) + option.hard_static
            key = (delta, -option.quality_score)
            if best_key is None or key < best_key:
                best_key = key
                best_index = option.plan_index
        selected.append(best_index)
        resource_counts.update(task.options[best_index].resource_counts)
    if start_offset == 0:
        return tuple(selected)
    restored = [0 for _ in tasks]
    for task_position, value in enumerate(selected):
        restored[(task_position + start_offset) % len(tasks)] = value
    return tuple(restored)


def _evaluate(chromosome: tuple[int, ...], tasks: list[TaskPlans]) -> Evaluated:
    teacher_counts: dict[int, int] = {}
    class_counts: dict[int, int] = {}
    room_counts: dict[int, int] = {}
    class_day_counts: Counter[ClassDayKey] = Counter()
    class_course_day_counts: Counter[ClassCourseDayKey] = Counter()
    task_day_counts: Counter[TaskDayKey] = Counter()
    conflicts = Counter()
    hard = 0
    quality = 0.0
    assignment_count = 0

    for gene, task in zip(chromosome, tasks):
        if gene < 0 or gene >= len(task.options):
            hard += 1
            conflicts["invalid_candidate"] += 1
            continue
        option = task.options[gene]
        conflicts["teacher"] += _add_duplicate_count(teacher_counts, option.teacher_slot_keys)
        conflicts["class"] += _add_duplicate_count(class_counts, option.class_slot_keys)
        conflicts["room"] += _add_duplicate_count(room_counts, option.room_slot_keys)
        class_day_counts.update(option.class_day_counts)
        class_course_day_counts.update(option.class_course_day_counts)
        task_day_counts.update(option.task_day_counts)
        hard += option.hard_static
        conflicts["hour_mismatch"] += option.hard_static
        quality += option.quality_score
        assignment_count += len(option.assignments)

    hard += conflicts["teacher"] + conflicts["class"] + conflicts["room"]

    beauty_penalty = _beauty_penalty(class_day_counts, class_course_day_counts, task_day_counts)
    quality -= beauty_penalty * 0.05
    return Evaluated(
        chromosome=chromosome,
        fitness=Fitness(
            hard_conflicts=hard,
            quality_score=round(quality, 6),
            beauty_penalty=round(beauty_penalty, 6),
            conflict_summary={
                "teacher": int(conflicts.get("teacher", 0)),
                "class": int(conflicts.get("class", 0)),
                "room": int(conflicts.get("room", 0)),
                "hour_mismatch": int(conflicts.get("hour_mismatch", 0)),
            },
            assignment_count=assignment_count,
        ),
    )


def _add_duplicate_count(counter: dict[int, int], keys: tuple[int, ...]) -> int:
    duplicates = 0
    for key in keys:
        previous = counter.get(key, 0)
        if previous:
            duplicates += 1
        counter[key] = previous + 1
    return duplicates


def _packed_slot_key(entity_id: int, week: int, day: int, period: int) -> int:
    return (((int(entity_id) * 64) + int(week)) * 8 + int(day)) * 8 + int(period)


def _beauty_penalty(
    class_day_counts: Counter[ClassDayKey],
    class_course_day_counts: Counter[ClassCourseDayKey],
    task_day_counts: Counter[TaskDayKey],
) -> float:
    penalty = 0.0
    for count in class_day_counts.values():
        if count > 3:
            penalty += (count - 3) * 2.0
    for count in class_course_day_counts.values():
        if count > 1:
            penalty += (count - 1) * 3.0
    for count in task_day_counts.values():
        if count > 1:
            penalty += (count - 1) * 1.5
    weekly_load: Counter[tuple[int, int]] = Counter()
    for (class_group_id, week, _day), count in class_day_counts.items():
        weekly_load[(class_group_id, week)] += count
    for (class_group_id, week), total in weekly_load.items():
        loads = [class_day_counts.get((class_group_id, week, day), 0) for day in range(1, 6)]
        if total > 0:
            penalty += (max(loads) - min(loads)) * 0.2
    return penalty


def _hard_delta(current: Counter[ResourceKey], addition: Counter[ResourceKey]) -> int:
    delta = 0
    for key, count in addition.items():
        before = current.get(key, 0)
        after = before + count
        delta += max(0, after - 1) - max(0, before - 1)
    return delta


def _collect_archive(archive: dict[tuple[int, ...], Evaluated], evaluated: list[Evaluated], scheme_count: int) -> None:
    for item in evaluated:
        archive[item.chromosome] = item
    best = sorted(archive.values(), key=lambda item: item.fitness.key)[: max(scheme_count * 4, scheme_count)]
    archive.clear()
    archive.update({item.chromosome: item for item in best})


def _tournament(evaluated: list[Evaluated], tournament_size: int, rng: random.Random) -> Evaluated:
    competitors = rng.sample(evaluated, min(tournament_size, len(evaluated)))
    return min(competitors, key=lambda item: item.fitness.key)


def _crossover(parent_a: tuple[int, ...], parent_b: tuple[int, ...], rng: random.Random) -> tuple[int, ...]:
    if len(parent_a) <= 1:
        return parent_a
    if rng.random() < 0.5:
        point = rng.randrange(1, len(parent_a))
        return parent_a[:point] + parent_b[point:]
    return tuple(a if rng.random() < 0.5 else b for a, b in zip(parent_a, parent_b))


def _mutate(
    chromosome: tuple[int, ...],
    tasks: list[TaskPlans],
    mutation_rate: float,
    rng: random.Random,
    conflicted_indexes: set[int],
) -> tuple[int, ...]:
    mutated = list(chromosome)
    for index, task in enumerate(tasks):
        rate = max(mutation_rate, 0.35) if index in conflicted_indexes else mutation_rate
        if len(task.options) > 1 and rng.random() < rate:
            mutated[index] = _different_gene(mutated[index], len(task.options), rng)
    return tuple(mutated)


def _repair(chromosome: tuple[int, ...], tasks: list[TaskPlans], *, max_tasks: int = DEFAULT_REPAIR_MAX_TASKS) -> tuple[int, ...]:
    current = _evaluate(chromosome, tasks)
    if current.fitness.hard_conflicts == 0 or max_tasks <= 0:
        return chromosome
    repaired = list(chromosome)
    conflict_indexes = sorted(_conflicted_task_indexes(current, tuple(repaired), tasks))[:max_tasks]
    for task_index in conflict_indexes:
        best = _evaluate(tuple(repaired), tasks)
        best_gene = repaired[task_index]
        for option in tasks[task_index].options:
            if option.plan_index == repaired[task_index]:
                continue
            trial = list(repaired)
            trial[task_index] = option.plan_index
            evaluated = _evaluate(tuple(trial), tasks)
            if evaluated.fitness.key < best.fitness.key:
                best = evaluated
                best_gene = option.plan_index
        repaired[task_index] = best_gene
        if best.fitness.hard_conflicts == 0:
            break
    return tuple(repaired)


def _conflicted_task_indexes(evaluated: Evaluated, chromosome: tuple[int, ...], tasks: list[TaskPlans]) -> set[int]:
    if evaluated.fitness.hard_conflicts == 0:
        return set()
    resource_usage: dict[ResourceKey, list[int]] = {}
    conflicted: set[int] = set()
    for task_index, (gene, task) in enumerate(zip(chromosome, tasks)):
        if gene < 0 or gene >= len(task.options):
            conflicted.add(task_index)
            continue
        option = task.options[gene]
        if option.hard_static:
            conflicted.add(task_index)
        for key in option.resource_counts:
            resource_usage.setdefault(key, []).append(task_index)
    for indexes in resource_usage.values():
        if len(indexes) > 1:
            conflicted.update(indexes)
    return conflicted


def _different_gene(current: int, pool_size: int, rng: random.Random) -> int:
    if pool_size <= 1:
        return current
    candidate = rng.randrange(pool_size - 1)
    if candidate >= current:
        candidate += 1
    return candidate


def _dedupe_population(
    population: list[tuple[int, ...]],
    tasks: list[TaskPlans],
    population_size: int,
    rng: random.Random,
) -> list[tuple[int, ...]]:
    if not tasks:
        return []
    search_space = 1
    for task in tasks:
        search_space *= max(1, len(task.options))
        if search_space >= population_size:
            break
    seen: set[tuple[int, ...]] = set()
    result: list[tuple[int, ...]] = []
    for chromosome in population:
        if chromosome not in seen:
            seen.add(chromosome)
            result.append(chromosome)
    target_unique = min(population_size, search_space)
    attempts = 0
    while len(result) < target_unique and attempts < population_size * 20:
        attempts += 1
        chromosome = tuple(rng.randrange(len(task.options)) for task in tasks)
        if chromosome not in seen:
            seen.add(chromosome)
            result.append(chromosome)
    while len(result) < population_size:
        result.append(result[len(result) % max(1, len(result))])
    return result[:population_size]


def _scheme_to_json(scheme_index: int, evaluated: Evaluated, tasks: list[TaskPlans]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for gene, task in zip(evaluated.chromosome, tasks):
        if 0 <= gene < len(task.options):
            items.extend(task.options[gene].assignments)
    items.sort(key=lambda item: (
        int(item.get("teaching_task_id") or 0),
        int(item.get("week_number") or 0),
        int(item.get("day_of_week") or 0),
        int(item.get("period_index") or 0),
    ))
    return {
        "scheme_index": scheme_index,
        "items": items,
        "hard_conflicts": evaluated.fitness.hard_conflicts,
        "quality_score": evaluated.fitness.quality_score,
        "beauty_penalty": evaluated.fitness.beauty_penalty,
        "conflict_summary": evaluated.fitness.conflict_summary,
        "chromosome": list(evaluated.chromosome),
    }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select V3 global plans with GA.")
    parser.add_argument("task_plans_path")
    parser.add_argument("--scheme-count", type=int, default=DEFAULT_SCHEME_COUNT)
    parser.add_argument("--population-size", type=int, default=DEFAULT_POPULATION_SIZE)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--elite-size", type=int, default=DEFAULT_ELITE_SIZE)
    parser.add_argument("--tournament-size", type=int, default=DEFAULT_TOURNAMENT_SIZE)
    parser.add_argument("--mutation-rate", type=float, default=DEFAULT_MUTATION_RATE)
    parser.add_argument("--repair-top-k", type=int, default=DEFAULT_REPAIR_TOP_K)
    parser.add_argument("--repair-max-tasks", type=int, default=DEFAULT_REPAIR_MAX_TASKS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    summary = select_global_plans_jsonl(
        args.task_plans_path,
        scheme_count=args.scheme_count,
        population_size=args.population_size,
        generations=args.generations,
        elite_size=args.elite_size,
        tournament_size=args.tournament_size,
        mutation_rate=args.mutation_rate,
        repair_top_k=args.repair_top_k,
        repair_max_tasks=args.repair_max_tasks,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
