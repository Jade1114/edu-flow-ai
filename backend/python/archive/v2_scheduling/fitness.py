"""Fitness evaluation for candidate-index chromosomes."""

from __future__ import annotations

from collections import Counter, defaultdict

from python.scheduling_v2.models import AssignmentRef, FitnessResult, ScheduleContext, SchedTask, TaskCandidate

HARD_CONFLICT_WEIGHT = 1_000_000.0


def expand_chromosome(
    chromosome: tuple[int, ...],
    pools: list[list[TaskCandidate]],
) -> tuple[AssignmentRef, ...]:
    assignments: list[AssignmentRef] = []
    for gene, pool in zip(chromosome, pools):
        if gene < 0 or gene >= len(pool):
            continue
        assignments.extend(pool[gene].assignments)
    return tuple(assignments)


def evaluate(
    chromosome: tuple[int, ...],
    context: ScheduleContext,
    pools: list[list[TaskCandidate]],
) -> FitnessResult:
    assignments = expand_chromosome(chromosome, pools)
    conflicts = Counter()
    hard = 0

    hard += _count_duplicate_conflicts(assignments, conflicts)
    hard += _count_hour_mismatches(assignments, context.tasks, conflicts)
    hard += _count_invalid_slots(assignments, context, conflicts)

    candidate_score = 0.0
    profile_penalty = 0.0
    for gene, pool in zip(chromosome, pools):
        if gene < 0 or gene >= len(pool):
            hard += 1
            conflicts["INVALID_CANDIDATE"] += 1
            continue
        candidate = pool[gene]
        candidate_score += candidate.score
        profile_penalty += candidate.teacher_profile_penalty

    quality = candidate_score - profile_penalty * context.scoring_config.get("profile_penalty_scale", 0.001)
    return FitnessResult(
        hard_conflicts=hard,
        quality_score=quality,
        conflict_summary=dict(conflicts),
        assignment_count=len(assignments),
    )


def fitness_key(result: FitnessResult) -> tuple[int, float]:
    return (result.hard_conflicts, -result.quality_score)


def _count_duplicate_conflicts(assignments: tuple[AssignmentRef, ...], conflicts: Counter) -> int:
    hard = 0
    teacher_slots: dict[tuple[int, int], int] = defaultdict(int)
    class_slots: dict[tuple[int, int], int] = defaultdict(int)
    room_slots: dict[tuple[int, int], int] = defaultdict(int)

    for assignment in assignments:
        teacher_slots[(assignment.teacher_id, assignment.time_slot_id)] += 1
        for class_group_id in assignment.class_group_ids:
            class_slots[(class_group_id, assignment.time_slot_id)] += 1
        room_slots[(assignment.classroom_id, assignment.time_slot_id)] += 1

    for counter, label in (
        (teacher_slots, "TEACHER_TIME"),
        (class_slots, "CLASS_GROUP_TIME"),
        (room_slots, "CLASSROOM_TIME"),
    ):
        for count in counter.values():
            if count > 1:
                delta = count - 1
                hard += delta
                conflicts[label] += delta
    return hard


def _count_hour_mismatches(
    assignments: tuple[AssignmentRef, ...],
    tasks: tuple[SchedTask, ...],
    conflicts: Counter,
) -> int:
    by_task = Counter(assignment.teaching_task_id for assignment in assignments)
    hard = 0
    for task in tasks:
        actual_hours = by_task.get(task.teaching_task_id, 0) * 2
        if actual_hours != task.total_hours:
            hard += 1
            conflicts["TEACHING_TASK_HOURS"] += 1
    return hard


def _count_invalid_slots(assignments: tuple[AssignmentRef, ...], context: ScheduleContext, conflicts: Counter) -> int:
    hard = 0
    for assignment in assignments:
        if assignment.time_slot_id not in context.allowed_time_slot_ids:
            hard += 1
            conflicts["TIME_DOMAIN"] += 1
    return hard
