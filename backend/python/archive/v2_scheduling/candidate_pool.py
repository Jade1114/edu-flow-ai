"""Build task-level scheduling candidates."""

from __future__ import annotations

from concurrent.futures import FIRST_EXCEPTION, ProcessPoolExecutor, wait
import logging
import random
import time
from typing import Any

from python.scheduling.enumerator import enumerate_template_sets
from python.scheduling.teacher_profiles import hard_unavailable_slots, profile_explanation, profile_penalty
from python.scheduling.types import day_period_to_slot
from python.scheduling_v2.models import AssignmentRef, ScheduleContext, SchedTask, TaskCandidate
from python.scheduling_v2.placement_ranker import placement_ranker_enabled, score_placements
from python.scheduling_v2.room_ranker import rank_rooms, room_ranker_enabled
from python.scheduling_v2.slot_ranker import rank_slots, slot_ranker_enabled

_log = logging.getLogger("ga")
STEP_LOG_THRESHOLD_MS = 300.0
_WORKER_CONTEXT: ScheduleContext | None = None
_WORKER_PARAMS: dict[str, int] | None = None


def build_candidate_pool(
    context: ScheduleContext,
    *,
    pool_size_per_task: int,
    room_top_n: int = 5,
    template_top_n: int = 12,
    slot_top_n: int = 18,
    candidate_workers: int = 1,
    local_expand_enabled: bool = True,
    local_expand_slot_limit: int = 12,
    local_expand_room_limit: int = 12,
    local_expand_max_added_per_task: int = 80,
) -> list[list[TaskCandidate]]:
    """Return candidate pools aligned with ``context.tasks`` order."""

    if candidate_workers <= 1 or len(context.tasks) <= 1:
        pools = _build_candidate_pool_serial(
            context,
            pool_size_per_task=pool_size_per_task,
            room_top_n=room_top_n,
            template_top_n=template_top_n,
            slot_top_n=slot_top_n,
        )
    else:
        pools = _build_candidate_pool_parallel(
            context,
            pool_size_per_task=pool_size_per_task,
            room_top_n=room_top_n,
            template_top_n=template_top_n,
            slot_top_n=slot_top_n,
            candidate_workers=candidate_workers,
        )
    if local_expand_enabled:
        pools = _expand_candidate_pool_local(
            context,
            pools,
            slot_limit=local_expand_slot_limit,
            room_limit=local_expand_room_limit,
            max_added_per_task=local_expand_max_added_per_task,
        )
    return pools


def _build_candidate_pool_serial(
    context: ScheduleContext,
    *,
    pool_size_per_task: int,
    room_top_n: int,
    template_top_n: int,
    slot_top_n: int,
) -> list[list[TaskCandidate]]:
    pools: list[list[TaskCandidate]] = []
    difficulty_counts: dict[str, int] = {"easy": 0, "normal": 0, "hard": 0, "critical": 0}
    started_at = time.perf_counter()
    for task_number, task in enumerate(context.tasks, start=1):
        task_started_at = time.perf_counter()
        candidates = _build_task_candidates(
            task,
            context,
            pool_size=pool_size_per_task,
            room_top_n=room_top_n,
            template_top_n=template_top_n,
            slot_top_n=slot_top_n,
        )
        if not candidates:
            raise ValueError(f"排课失败：教学任务 {task.teaching_task_id} 没有可行候选")
        difficulty = str(candidates[0].metadata.get("difficulty") or "unknown")
        difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
        pools.append(candidates)
        elapsed_ms = (time.perf_counter() - task_started_at) * 1000
        if elapsed_ms >= 1000 or task_number == 1 or task_number % 25 == 0:
            _log.info(
                "Candidate task done: %s/%s task_id=%s candidates=%s difficulty=%s elapsed_ms=%.1f",
                task_number,
                len(context.tasks),
                task.teaching_task_id,
                len(candidates),
                difficulty,
                elapsed_ms,
            )
    pool_sizes = [len(pool) for pool in pools]
    _log.info(
        "Candidate pool built: tasks=%s total_candidates=%s min=%s max=%s avg=%.1f difficulty=%s "
        "room_ranker_enabled=%s slot_ranker_enabled=%s placement_ranker_enabled=%s elapsed_ms=%.1f",
        len(pools),
        sum(pool_sizes),
        min(pool_sizes) if pool_sizes else 0,
        max(pool_sizes) if pool_sizes else 0,
        sum(pool_sizes) / max(1, len(pool_sizes)),
        difficulty_counts,
        room_ranker_enabled(),
        slot_ranker_enabled(),
        placement_ranker_enabled(),
        (time.perf_counter() - started_at) * 1000,
    )
    return pools


def _build_candidate_pool_parallel(
    context: ScheduleContext,
    *,
    pool_size_per_task: int,
    room_top_n: int,
    template_top_n: int,
    slot_top_n: int,
    candidate_workers: int,
) -> list[list[TaskCandidate]]:
    total_tasks = len(context.tasks)
    workers = max(1, min(candidate_workers, total_tasks))
    started_at = time.perf_counter()
    _log.info(
        "Candidate pool parallel start: tasks=%s workers=%s pool_size=%s room_top_n=%s template_top_n=%s slot_top_n=%s",
        total_tasks,
        workers,
        pool_size_per_task,
        room_top_n,
        template_top_n,
        slot_top_n,
    )
    pools: list[list[TaskCandidate] | None] = [None] * total_tasks
    task_elapsed_ms: list[float] = []
    difficulty_counts: dict[str, int] = {"easy": 0, "normal": 0, "hard": 0, "critical": 0}
    params = {
        "pool_size": int(pool_size_per_task),
        "room_top_n": int(room_top_n),
        "template_top_n": int(template_top_n),
        "slot_top_n": int(slot_top_n),
    }

    try:
        executor = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_candidate_worker,
            initargs=(context, params),
        )
    except OSError as exc:
        _log.warning("Candidate pool parallel unavailable, fallback to serial: %s", exc)
        return _build_candidate_pool_serial(
            context,
            pool_size_per_task=pool_size_per_task,
            room_top_n=room_top_n,
            template_top_n=template_top_n,
            slot_top_n=slot_top_n,
        )

    with executor:
        future_to_index = {
            executor.submit(_build_task_candidates_in_worker, index, task): index
            for index, task in enumerate(context.tasks)
        }
        pending = set(future_to_index)
        completed_count = 0
        while pending:
            done, pending = wait(pending, return_when=FIRST_EXCEPTION)
            for future in done:
                task_index = future_to_index[future]
                task = context.tasks[task_index]
                try:
                    result_index, candidates, elapsed_ms = future.result()
                except Exception as exc:
                    for pending_future in pending:
                        pending_future.cancel()
                    raise ValueError(
                        f"排课失败：教学任务 {task.teaching_task_id} 候选集构造失败，"
                        f"index={task_index + 1}/{total_tasks}，原因={exc}"
                    ) from exc

                if not candidates:
                    for pending_future in pending:
                        pending_future.cancel()
                    raise ValueError(
                        f"排课失败：教学任务 {task.teaching_task_id} 候选集构造失败，"
                        f"index={task_index + 1}/{total_tasks}，原因=没有可行候选"
                    )

                pools[result_index] = candidates
                elapsed = float(elapsed_ms)
                task_elapsed_ms.append(elapsed)
                difficulty = str(candidates[0].metadata.get("difficulty") or "unknown")
                difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
                completed_count += 1
                if elapsed >= 1000 or completed_count == 1 or completed_count % 25 == 0:
                    _log.info(
                        "Candidate task done: %s/%s task_id=%s candidates=%s difficulty=%s elapsed_ms=%.1f worker=process",
                        completed_count,
                        total_tasks,
                        task.teaching_task_id,
                        len(candidates),
                        difficulty,
                        elapsed,
                    )

    completed_pools = [pool for pool in pools if pool is not None]
    if len(completed_pools) != total_tasks:
        missing = [index + 1 for index, pool in enumerate(pools) if pool is None]
        raise ValueError(f"排课失败：候选集并发构造结果缺失，missing_indexes={missing[:10]}")

    pool_sizes = [len(pool) for pool in completed_pools]
    total_elapsed_ms = (time.perf_counter() - started_at) * 1000
    _log.info(
        "Candidate pool parallel end: tasks=%s workers=%s total_candidates=%s min=%s max=%s avg=%.1f "
        "avg_task_ms=%.1f difficulty=%s elapsed_ms=%.1f",
        total_tasks,
        workers,
        sum(pool_sizes),
        min(pool_sizes) if pool_sizes else 0,
        max(pool_sizes) if pool_sizes else 0,
        sum(pool_sizes) / max(1, len(pool_sizes)),
        sum(task_elapsed_ms) / max(1, len(task_elapsed_ms)),
        difficulty_counts,
        total_elapsed_ms,
    )
    _log.info(
        "Candidate pool built: tasks=%s total_candidates=%s min=%s max=%s avg=%.1f difficulty=%s "
        "room_ranker_enabled=%s slot_ranker_enabled=%s placement_ranker_enabled=%s elapsed_ms=%.1f",
        total_tasks,
        sum(pool_sizes),
        min(pool_sizes) if pool_sizes else 0,
        max(pool_sizes) if pool_sizes else 0,
        sum(pool_sizes) / max(1, len(pool_sizes)),
        difficulty_counts,
        room_ranker_enabled(),
        slot_ranker_enabled(),
        placement_ranker_enabled(),
        total_elapsed_ms,
    )
    return completed_pools


def _expand_candidate_pool_local(
    context: ScheduleContext,
    pools: list[list[TaskCandidate]],
    *,
    slot_limit: int,
    room_limit: int,
    max_added_per_task: int,
) -> list[list[TaskCandidate]]:
    if max_added_per_task <= 0:
        return pools
    started_at = time.perf_counter()
    expanded: list[list[TaskCandidate]] = []
    total_added = 0
    tasks_by_id = {task.teaching_task_id: task for task in context.tasks}
    day_periods = sorted({(int(slot["day_of_week"]), int(slot["period_index"])) for slot in context.time_slots})
    for pool in pools:
        if not pool:
            expanded.append(pool)
            continue
        task = tasks_by_id.get(pool[0].teaching_task_id)
        if task is None:
            expanded.append(pool)
            continue
        next_pool, stats = _expand_task_candidates_local(
            task,
            context,
            pool,
            day_periods=day_periods,
            slot_limit=slot_limit,
            room_limit=room_limit,
            max_added=max_added_per_task,
        )
        total_added += stats["added"]
        expanded.append(next_pool)
        if stats["added"] > 0:
            _log.info(
                "Candidate local expansion: task_id=%s added=%s slot_buckets=%s room_buckets=%s total_candidates=%s",
                task.teaching_task_id,
                stats["added"],
                stats["slot_buckets"],
                stats["room_buckets"],
                len(next_pool),
            )
    _log.info(
        "Candidate local expansion done: tasks=%s added=%s elapsed_ms=%.1f",
        len(pools),
        total_added,
        (time.perf_counter() - started_at) * 1000,
    )
    return expanded


def _expand_task_candidates_local(
    task: SchedTask,
    context: ScheduleContext,
    pool: list[TaskCandidate],
    *,
    day_periods: list[tuple[int, int]],
    slot_limit: int,
    room_limit: int,
    max_added: int,
) -> tuple[list[TaskCandidate], dict[str, int]]:
    result = list(pool)
    seen = {_candidate_identity(candidate) for candidate in result}
    slot_ranked = rank_slots(task, day_periods, top_n=max(1, slot_limit))
    room_ranked = _rank_rooms(task, context.classrooms)[:max(1, room_limit)]
    slot_buckets = len({_slot_signature(candidate) for candidate in pool})
    room_buckets = len({_room_signature(candidate) for candidate in pool})

    for base in pool[: min(len(pool), 24)]:
        if len(result) - len(pool) >= max_added:
            break
        for room in room_ranked:
            room_id = int(room["id"])
            if room_id in {assignment.classroom_id for assignment in base.assignments}:
                continue
            candidate = _clone_candidate_with_room(base, room_id, len(result))
            if _append_expanded_candidate(result, seen, candidate):
                if len(result) - len(pool) >= max_added:
                    break
        if len(result) - len(pool) >= max_added:
            break
        for day, period, _score in slot_ranked:
            candidate = _clone_candidate_with_single_slot_shift(base, context, int(day), int(period), len(result))
            if candidate is not None:
                _append_expanded_candidate(result, seen, candidate)
            if len(result) - len(pool) >= max_added:
                break

    result.sort(key=lambda candidate: (-candidate.score, candidate.teacher_profile_penalty, candidate.template_signature))
    result = [_renumber_candidate(candidate, index) for index, candidate in enumerate(result)]
    return result, {
        "added": len(result) - len(pool),
        "slot_buckets": slot_buckets,
        "room_buckets": room_buckets,
    }


def _append_expanded_candidate(
    result: list[TaskCandidate],
    seen: set[tuple[tuple[int, int], ...]],
    candidate: TaskCandidate,
) -> bool:
    identity = _candidate_identity(candidate)
    if identity in seen:
        return False
    seen.add(identity)
    result.append(candidate)
    return True


def _candidate_identity(candidate: TaskCandidate) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((assignment.time_slot_id, assignment.classroom_id) for assignment in candidate.assignments))


def _slot_signature(candidate: TaskCandidate) -> tuple[int, ...]:
    return tuple(sorted(assignment.time_slot_id for assignment in candidate.assignments))


def _room_signature(candidate: TaskCandidate) -> tuple[int, ...]:
    return tuple(sorted(assignment.classroom_id for assignment in candidate.assignments))


def _clone_candidate_with_room(base: TaskCandidate, room_id: int, candidate_index: int) -> TaskCandidate:
    assignments = tuple(
        AssignmentRef(
            teaching_task_id=assignment.teaching_task_id,
            teacher_id=assignment.teacher_id,
            class_group_ids=assignment.class_group_ids,
            classroom_id=room_id,
            time_slot_id=assignment.time_slot_id,
            week_number=assignment.week_number,
            day_of_week=assignment.day_of_week,
            period_index=assignment.period_index,
            room_rank_score=assignment.room_rank_score,
            teacher_profile_penalty=assignment.teacher_profile_penalty,
            teacher_profile_penalty_explanation=assignment.teacher_profile_penalty_explanation,
        )
        for assignment in base.assignments
    )
    return TaskCandidate(
        teaching_task_id=base.teaching_task_id,
        candidate_index=candidate_index,
        assignments=assignments,
        template_signature=base.template_signature,
        score=base.score - 0.0001,
        room_rank_score=base.room_rank_score,
        teacher_profile_penalty=base.teacher_profile_penalty,
        metadata={**base.metadata, "local_expansion": "room"},
    )


def _clone_candidate_with_single_slot_shift(
    base: TaskCandidate,
    context: ScheduleContext,
    day: int,
    period: int,
    candidate_index: int,
) -> TaskCandidate | None:
    if any(assignment.day_of_week == day and assignment.period_index == period for assignment in base.assignments):
        return None
    grouped: dict[tuple[int, int], list[AssignmentRef]] = {}
    for assignment in base.assignments:
        grouped.setdefault((assignment.day_of_week, assignment.period_index), []).append(assignment)
    if not grouped:
        return None
    # Move the first lesson fragment only; this keeps the weekly template shape stable.
    source_key = sorted(grouped, key=lambda key: (len(grouped[key]), key[0], key[1]))[0]
    new_assignments: list[AssignmentRef] = []
    used_slots: set[int] = set()
    for assignment in base.assignments:
        target_day, target_period = (day, period) if (assignment.day_of_week, assignment.period_index) == source_key else (assignment.day_of_week, assignment.period_index)
        slot_ref = context.slot_by_coord.get((assignment.week_number, target_day, target_period))
        if slot_ref is None or slot_ref.id in used_slots:
            return None
        used_slots.add(slot_ref.id)
        new_assignments.append(AssignmentRef(
            teaching_task_id=assignment.teaching_task_id,
            teacher_id=assignment.teacher_id,
            class_group_ids=assignment.class_group_ids,
            classroom_id=assignment.classroom_id,
            time_slot_id=slot_ref.id,
            week_number=assignment.week_number,
            day_of_week=target_day,
            period_index=target_period,
            room_rank_score=assignment.room_rank_score,
            teacher_profile_penalty=assignment.teacher_profile_penalty,
            teacher_profile_penalty_explanation=assignment.teacher_profile_penalty_explanation,
        ))
    return TaskCandidate(
        teaching_task_id=base.teaching_task_id,
        candidate_index=candidate_index,
        assignments=tuple(new_assignments),
        template_signature=base.template_signature,
        score=base.score - 0.0002,
        room_rank_score=base.room_rank_score,
        teacher_profile_penalty=base.teacher_profile_penalty,
        metadata={**base.metadata, "local_expansion": "slot"},
    )


def _init_candidate_worker(context: ScheduleContext, params: dict[str, int]) -> None:
    global _WORKER_CONTEXT, _WORKER_PARAMS
    _WORKER_CONTEXT = context
    _WORKER_PARAMS = params


def _build_task_candidates_in_worker(
    task_index: int,
    task: SchedTask,
) -> tuple[int, list[TaskCandidate], float]:
    if _WORKER_CONTEXT is None or _WORKER_PARAMS is None:
        raise RuntimeError("candidate worker is not initialized")
    started_at = time.perf_counter()
    candidates = _build_task_candidates(
        task,
        _WORKER_CONTEXT,
        pool_size=int(_WORKER_PARAMS["pool_size"]),
        room_top_n=int(_WORKER_PARAMS["room_top_n"]),
        template_top_n=int(_WORKER_PARAMS["template_top_n"]),
        slot_top_n=int(_WORKER_PARAMS["slot_top_n"]),
    )
    return task_index, candidates, (time.perf_counter() - started_at) * 1000


def _build_task_candidates(
    task: SchedTask,
    context: ScheduleContext,
    *,
    pool_size: int,
    room_top_n: int,
    template_top_n: int,
    slot_top_n: int,
) -> list[TaskCandidate]:
    if task.total_lessons <= 0:
        raise ValueError(f"排课失败：教学任务 {task.teaching_task_id} 课时数无效")

    total_started_at = time.perf_counter()
    _log.info(
        "Candidate task start: task_id=%s lessons=%s hours=%s teacher=%s class_groups=%s",
        task.teaching_task_id,
        task.total_lessons,
        task.total_hours,
        task.teacher_id,
        task.class_group_ids,
    )
    available_weeks = sorted({int(slot["week_number"]) for slot in context.time_slots})
    template_started_at = time.perf_counter()
    template_sets = enumerate_template_sets(task.total_lessons, available_weeks)[:template_top_n]
    template_ms = (time.perf_counter() - template_started_at) * 1000
    _log.info(
        "Candidate task templates: task_id=%s total_lessons=%s template_top_n=%s selected=%s elapsed_ms=%.1f",
        task.teaching_task_id,
        task.total_lessons,
        template_top_n,
        len(template_sets),
        template_ms,
    )
    if not template_sets:
        return []

    difficulty_started_at = time.perf_counter()
    difficulty = _task_difficulty(task, context)
    pool_target = _dynamic_pool_size(pool_size, difficulty)
    room_limit = _dynamic_room_limit(room_top_n, difficulty)
    slot_limit = _dynamic_slot_limit(slot_top_n, difficulty, context)
    difficulty_ms = (time.perf_counter() - difficulty_started_at) * 1000
    _log_step(
        "Candidate task difficulty",
        task.teaching_task_id,
        difficulty_ms,
        difficulty=difficulty,
        pool_target=pool_target,
        room_limit=room_limit,
        slot_limit=slot_limit,
    )

    room_started_at = time.perf_counter()
    rooms = _rank_rooms(task, context.classrooms)[:room_limit]
    room_ms = (time.perf_counter() - room_started_at) * 1000
    _log.info(
        "Candidate task rooms: task_id=%s feasible_selected=%s room_limit=%s rank_source=%s top_room_score=%.4f elapsed_ms=%.1f",
        task.teaching_task_id,
        len(rooms),
        room_limit,
        rooms[0].get("_rank_source") if rooms else "none",
        float(rooms[0].get("_rank_score") or 0.0) if rooms else 0.0,
        room_ms,
    )
    if not rooms:
        return []

    candidates: list[TaskCandidate] = []
    seen: set[tuple[tuple[int, int], ...]] = set()
    slot_ms = 0.0
    combo_ms = 0.0
    expand_ms = 0.0
    combo_count = 0

    for template_set_index, template_set in enumerate(template_sets):
        template_set_started_at = time.perf_counter()
        _log.info(
            "Candidate template_set start: task_id=%s ts=%s/%s templates=%s current_candidates=%s",
            task.teaching_task_id,
            template_set_index + 1,
            len(template_sets),
            len(template_set.templates),
            len(candidates),
        )
        slot_started_at = time.perf_counter()
        slot_options = [
            _rank_slot_options(task, template, rooms, context, slot_limit)
            for template in template_set.templates
        ]
        slot_elapsed_ms = (time.perf_counter() - slot_started_at) * 1000
        slot_ms += slot_elapsed_ms
        _log.info(
            "Candidate template_set slots: task_id=%s ts=%s/%s option_counts=%s elapsed_ms=%.1f",
            task.teaching_task_id,
            template_set_index + 1,
            len(template_sets),
            [len(options) for options in slot_options],
            slot_elapsed_ms,
        )
        if any(not options for options in slot_options):
            _log.info(
                "Candidate template_set skipped: task_id=%s ts=%s/%s reason=empty_slot_options",
                task.teaching_task_id,
                template_set_index + 1,
                len(template_sets),
            )
            continue

        combo_started_at = time.perf_counter()
        combos = _candidate_combinations(
            slot_options,
            limit=max(pool_target * 2, 24),
            max_unique_slots=slot_limit,
            max_rooms_per_slot=_dynamic_rooms_per_slot(difficulty),
            seed=task.teaching_task_id * 1_000_003 + template_set_index * 9176,
        )
        combo_elapsed_ms = (time.perf_counter() - combo_started_at) * 1000
        combo_ms += combo_elapsed_ms
        combo_count += len(combos)
        _log.info(
            "Candidate template_set combos: task_id=%s ts=%s/%s combos=%s limit=%s elapsed_ms=%.1f",
            task.teaching_task_id,
            template_set_index + 1,
            len(template_sets),
            len(combos),
            max(pool_target * 2, 24),
            combo_elapsed_ms,
        )

        expand_started_at = time.perf_counter()
        before_expand = len(candidates)
        for combo in combos:
            signature = tuple(sorted((slot_id, room_id) for slot_id, room_id, _score, _pen, _exp in combo))
            if signature in seen:
                continue
            seen.add(signature)
            assignments: list[AssignmentRef] = []
            score_sum = 0.0
            profile_penalty_sum = 0.0
            explanations: list[str] = []

            valid = True
            for template_index, (slot_id, room_id, score, penalty, explanation) in enumerate(combo):
                template = template_set.templates[template_index]
                day = slot_id // 5 + 1
                period = slot_id % 5 + 1
                if (day, period) in hard_unavailable_slots(task.teacher_profile):
                    valid = False
                    break
                for week in template.weeks_list:
                    slot_ref = context.slot_by_coord.get((week, day, period))
                    if slot_ref is None:
                        valid = False
                        break
                    assignments.append(AssignmentRef(
                        teaching_task_id=task.teaching_task_id,
                        teacher_id=task.teacher_id,
                        class_group_ids=task.class_group_ids,
                        classroom_id=room_id,
                        time_slot_id=slot_ref.id,
                        week_number=week,
                        day_of_week=day,
                        period_index=period,
                        room_rank_score=score,
                        teacher_profile_penalty=penalty,
                        teacher_profile_penalty_explanation=explanation,
                    ))
                if not valid:
                    break
                score_sum += score * len(template.weeks_list)
                profile_penalty_sum += penalty * len(template.weeks_list)
                if explanation:
                    explanations.append(explanation)

            if not valid or len(assignments) != task.total_lessons:
                continue

            avg_room_rank_score = score_sum / max(1, len(assignments))
            normalized_profile_penalty = profile_penalty_sum / max(1, len(assignments), 100)
            quality = avg_room_rank_score - normalized_profile_penalty * context.scoring_config.get("profile_penalty_scale", 0.001)
            candidates.append(TaskCandidate(
                teaching_task_id=task.teaching_task_id,
                candidate_index=len(candidates),
                assignments=tuple(assignments),
                template_signature=f"ts{template_set_index}:" + ",".join(
                    "-".join(str(week) for week in template.weeks_list)
                    for template in template_set.templates
                ),
                score=quality,
                room_rank_score=avg_room_rank_score,
                teacher_profile_penalty=profile_penalty_sum,
                metadata={
                    "template_set_index": template_set_index,
                    "template_penalty": template_set.penalty,
                    "difficulty": difficulty,
                    "teacher_profile_explanations": explanations,
                },
            ))
            if len(candidates) >= pool_target * 4:
                break
        expand_elapsed_ms = (time.perf_counter() - expand_started_at) * 1000
        expand_ms += expand_elapsed_ms
        _log.info(
            "Candidate template_set expand: task_id=%s ts=%s/%s added=%s total_candidates=%s elapsed_ms=%.1f total_ts_ms=%.1f",
            task.teaching_task_id,
            template_set_index + 1,
            len(template_sets),
            len(candidates) - before_expand,
            len(candidates),
            expand_elapsed_ms,
            (time.perf_counter() - template_set_started_at) * 1000,
        )
        if len(candidates) >= pool_target * 4:
            _log.info(
                "Candidate task early_stop: task_id=%s reason=raw_candidate_budget raw=%s budget=%s",
                task.teaching_task_id,
                len(candidates),
                pool_target * 4,
            )
            break

    sort_started_at = time.perf_counter()
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.teacher_profile_penalty, candidate.template_signature))
    selected = candidates[:pool_target]
    primary_cut = min(len(selected), max(40, pool_target // 2))
    sort_ms = (time.perf_counter() - sort_started_at) * 1000
    total_ms = (time.perf_counter() - total_started_at) * 1000
    if total_ms >= 1000:
        _log.info(
            "Candidate task profile: task_id=%s difficulty=%s lessons=%s templates=%s rooms=%s pool_target=%s "
            "selected=%s raw=%s combos=%s ms={template:%.1f,difficulty:%.1f,room:%.1f,slot:%.1f,combo:%.1f,expand:%.1f,sort:%.1f,total:%.1f}",
            task.teaching_task_id,
            difficulty,
            task.total_lessons,
            len(template_sets),
            len(rooms),
            pool_target,
            len(selected),
            len(candidates),
            combo_count,
            template_ms,
            difficulty_ms,
            room_ms,
            slot_ms,
            combo_ms,
            expand_ms,
            sort_ms,
            total_ms,
        )
    else:
        _log.info(
            "Candidate task profile: task_id=%s difficulty=%s selected=%s raw=%s combos=%s total_ms=%.1f",
            task.teaching_task_id,
            difficulty,
            len(selected),
            len(candidates),
            combo_count,
            total_ms,
        )
    return [
        _renumber_candidate(_with_tier(candidate, "primary" if index < primary_cut else "fallback"), index)
        for index, candidate in enumerate(selected)
    ]


def _rank_rooms(task: SchedTask, classrooms: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    return rank_rooms(task, classrooms)


def _rank_slot_options(
    task: SchedTask,
    template,
    rooms: list[dict[str, Any]],
    context: ScheduleContext,
    limit: int,
) -> list[tuple[int, int, float, float, str]]:
    """Return (slot_id, room_id, placement_score, penalty, explanation)."""
    started_at = time.perf_counter()

    day_periods = sorted({(int(slot["day_of_week"]), int(slot["period_index"])) for slot in context.time_slots})
    slot_scores = rank_slots(task, day_periods)
    slot_score_map: dict[tuple[int, int], float] = {(d, p): s for d, p, s in slot_scores}
    if not slot_scores:
        return []
    slot_model_enabled = slot_ranker_enabled()
    placement_model_enabled = placement_ranker_enabled()
    top_slot_score = max((score for _day, _period, score in slot_scores), default=0.0)

    hard_unavailable = hard_unavailable_slots(task.teacher_profile) if task.teacher_profile else set()
    options: list[tuple[float, int, int, float, float, str]] = []
    placement_inputs: list[dict[str, Any]] = []

    for day, period in day_periods:
        if (day, period) in hard_unavailable:
            continue
        slot_id = day_period_to_slot(day, period)
        penalty, breakdown = profile_penalty(task.teacher_profile, slot_id)

        for room in rooms:
            placement_inputs.append({
                "room_id": int(room["id"]),
                "room_name": room.get("name") or room.get("room_name") or room.get("classroom_name") or "",
                "room_type": room.get("classroom_type") or room.get("room_type") or "",
                "room_capacity": room.get("capacity") or room.get("room_capacity") or 0,
                "capacity": room.get("capacity") or room.get("room_capacity") or 0,
                "building": room.get("building") or room.get("name") or "",
                "day": day,
                "period": period,
                "slot_id": slot_id,
                "slot_score": slot_score_map.get((day, period), 0.0),
                "teacher_profile_penalty": penalty,
                "teacher_profile_explanation": profile_explanation(breakdown),
            })

    placement_weight = float(context.scoring_config.get("placement_ranker_weight", 1.0))
    profile_penalty_scale = float(context.scoring_config.get("profile_penalty_scale", 0.001))
    for placement, placement_score in score_placements(task, placement_inputs):
        slot_id = int(placement["slot_id"])
        room_id = int(placement["room_id"])
        penalty = float(placement["teacher_profile_penalty"])
        penalty_part = penalty * profile_penalty_scale
        total = float(placement_score) * placement_weight - penalty_part
        options.append((
            total,
            slot_id,
            room_id,
            float(placement_score),
            penalty,
            str(placement.get("teacher_profile_explanation") or ""),
        ))

    options.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected = _select_covered_slot_options(options, limit, task.teaching_task_id)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    _log_step(
        "Candidate slot options",
        task.teaching_task_id,
        elapsed_ms,
        ranked_slots=len(slot_scores),
        slot_model_enabled=slot_model_enabled,
        placement_model_enabled=placement_model_enabled,
        top_slot_score=round(top_slot_score, 4),
        day_periods=len(day_periods),
        rooms=len(rooms),
        raw=len(options),
        selected=len(selected),
        coverage_selected=len({slot_id for _total, slot_id, _room_id, _score, _penalty, _exp in selected}),
    )
    return [(slot_id, room_id, room_rank_score, penalty, explanation) for _total, slot_id, room_id, room_rank_score, penalty, explanation in selected]


def _candidate_combinations(
    slot_options: list[list[tuple[int, int, float, float, str]]],
    *,
    limit: int,
    max_unique_slots: int = 16,
    max_rooms_per_slot: int = 4,
    seed: int = 0,
) -> list[tuple[tuple[int, int, float, float, str], ...]]:
    if not slot_options:
        return []
    grouped_options = [
        _group_options_by_slot(options, max_unique_slots=max_unique_slots, max_rooms_per_slot=max_rooms_per_slot)
        for options in slot_options
    ]
    if any(not options for options in grouped_options):
        return []

    slot_choices = [list(group.keys()) for group in grouped_options]
    combo_budget = max(limit * 3, limit + 16)
    rng = random.Random(seed)
    combos: list[tuple[float, tuple[tuple[int, int, float, float, str], ...]]] = []
    seen_slots: set[tuple[int, ...]] = set()

    def add_combo(slots: list[int], variant_seed: int) -> None:
        if len(set(slots)) < len(slots):
            return
        signature = tuple(slots)
        if signature in seen_slots:
            return
        seen_slots.add(signature)
        values = tuple(
            _pick_room_variant(grouped_options[index][slot_id], variant_seed + index)
            for index, slot_id in enumerate(slots)
        )
        score = sum(value[2] - value[3] * 0.001 for value in values)
        combos.append((score, values))

    # A few deterministic high-quality/rotated combinations.
    for variant in range(min(24, combo_budget)):
        slots: list[int] = []
        used: set[int] = set()
        for index, choices in enumerate(slot_choices):
            choice = _pick_distinct_slot(choices, used, variant + index)
            if choice is None:
                break
            slots.append(choice)
            used.add(choice)
        if len(slots) == len(slot_choices):
            add_combo(slots, variant)
        if len(combos) >= combo_budget:
            break

    # Budgeted random/GRASP-style samples avoid the slot^template_count explosion.
    attempts = 0
    max_attempts = combo_budget * 8
    while len(combos) < combo_budget and attempts < max_attempts:
        attempts += 1
        slots = []
        used: set[int] = set()
        order = list(range(len(slot_choices)))
        rng.shuffle(order)
        picked_by_index: dict[int, int] = {}
        for index in order:
            choices = slot_choices[index]
            top_span = min(len(choices), max(4, len(choices) // 2))
            start = rng.randrange(top_span)
            choice = _pick_distinct_slot(choices, used, start)
            if choice is None:
                break
            picked_by_index[index] = choice
            used.add(choice)
        if len(picked_by_index) != len(slot_choices):
            continue
        slots = [picked_by_index[index] for index in range(len(slot_choices))]
        add_combo(slots, rng.randrange(max_rooms_per_slot))

    combos.sort(key=lambda item: -item[0])
    return [values for _score, values in combos[:limit]]


def _pick_distinct_slot(choices: list[int], used: set[int], start: int) -> int | None:
    if not choices:
        return None
    for offset in range(len(choices)):
        slot_id = choices[(start + offset) % len(choices)]
        if slot_id not in used:
            return slot_id
    return None


def _log_step(message: str, task_id: int, elapsed_ms: float, **fields: Any) -> None:
    if elapsed_ms < STEP_LOG_THRESHOLD_MS:
        return
    extras = " ".join(f"{key}={value}" for key, value in fields.items())
    _log.info("%s: task_id=%s elapsed_ms=%.1f %s", message, task_id, elapsed_ms, extras)


def _group_options_by_slot(
    options: list[tuple[int, int, float, float, str]],
    *,
    max_unique_slots: int,
    max_rooms_per_slot: int,
) -> dict[int, list[tuple[int, int, float, float, str]]]:
    """Keep several strong rooms per day/period without letting one slot dominate."""

    result: dict[int, list[tuple[int, int, float, float, str]]] = {}
    for option in options:
        slot_id = option[0]
        if slot_id not in result and len(result) >= max_unique_slots:
            continue
        room_options = result.setdefault(slot_id, [])
        if len(room_options) >= max_rooms_per_slot:
            continue
        room_options.append(option)
    return result


def _select_covered_slot_options(
    options: list[tuple[float, int, int, float, float, str]],
    limit: int,
    rotation_key: int,
) -> list[tuple[float, int, int, float, float, str]]:
    """Select high-scoring options while preserving day/period coverage."""

    if len(options) <= limit:
        return options

    selected: list[tuple[float, int, int, float, float, str]] = []
    seen: set[tuple[int, int]] = set()

    def add(option: tuple[float, int, int, float, float, str]) -> None:
        key = (option[1], option[2])
        if key not in seen and len(selected) < limit:
            seen.add(key)
            selected.append(option)

    for option in options[: max(1, limit // 2)]:
        add(option)

    best_by_day: dict[int, tuple[float, int, int, float, float, str]] = {}
    best_by_period: dict[int, tuple[float, int, int, float, float, str]] = {}
    best_by_slot: dict[int, tuple[float, int, int, float, float, str]] = {}
    for option in options:
        slot_id = option[1]
        day = slot_id // 5 + 1
        period = slot_id % 5 + 1
        best_by_day.setdefault(day, option)
        best_by_period.setdefault(period, option)
        best_by_slot.setdefault(slot_id, option)

    for option in best_by_day.values():
        add(option)
    for option in best_by_period.values():
        add(option)

    rotated_slots = list(best_by_slot.values())
    if rotated_slots:
        offset = rotation_key % len(rotated_slots)
        rotated_slots = rotated_slots[offset:] + rotated_slots[:offset]
    for option in rotated_slots:
        add(option)

    for option in options:
        add(option)
        if len(selected) >= limit:
            break
    return selected


def _pick_room_variant(
    options: list[tuple[int, int, float, float, str]],
    variant: int,
) -> tuple[int, int, float, float, str]:
    return options[variant % len(options)]


def _rule_slot_score(day: int, period: int, config: dict[str, Any]) -> float:
    score = 0.0
    if period == 1:
        score -= float(config.get("early_period_penalty") or 0.0)
    if period >= 4:
        score -= float(config.get("late_period_penalty") or 0.0)
    if day >= 6:
        score -= float(config.get("weekend_penalty") or 0.0)
    return score


def _task_difficulty(task: SchedTask, context: ScheduleContext) -> str:
    day_period_count = len({(int(slot["day_of_week"]), int(slot["period_index"])) for slot in context.time_slots})
    feasible_room_count = len(_rank_rooms(task, context.classrooms))
    score = 0
    if task.total_lessons >= 16:
        score += 2
    elif task.total_lessons >= 8:
        score += 1
    if len(task.class_group_ids) >= 2:
        score += 1
    if task.required_room_type:
        score += 1
    if day_period_count <= 20:
        score += 1
    if feasible_room_count <= 5:
        score += 2
    elif feasible_room_count <= 12:
        score += 1

    if score >= 5:
        return "critical"
    if score >= 3:
        return "hard"
    if score >= 1:
        return "normal"
    return "easy"


def _dynamic_pool_size(pool_size: int, difficulty: str) -> int:
    target = {
        "easy": 40,
        "normal": 80,
        "hard": 120,
        "critical": 180,
    }[difficulty]
    return max(20, min(pool_size, target))


def _dynamic_room_limit(base: int, difficulty: str) -> int:
    target = {
        "easy": 8,
        "normal": 15,
        "hard": 25,
        "critical": 40,
    }[difficulty]
    return max(base, target)


def _dynamic_slot_limit(base: int, difficulty: str, context: ScheduleContext) -> int:
    day_period_count = len({(int(slot["day_of_week"]), int(slot["period_index"])) for slot in context.time_slots})
    target = {
        "easy": 16,
        "normal": 30,
        "hard": 60,
        "critical": day_period_count,
    }[difficulty]
    return max(1, min(day_period_count, max(base, target)))


def _dynamic_rooms_per_slot(difficulty: str) -> int:
    return {
        "easy": 4,
        "normal": 5,
        "hard": 6,
        "critical": 8,
    }[difficulty]


def _with_tier(candidate: TaskCandidate, tier: str) -> TaskCandidate:
    metadata = dict(candidate.metadata)
    metadata["tier"] = tier
    fallback_penalty = 0.015 if tier == "fallback" else 0.0
    return TaskCandidate(
        teaching_task_id=candidate.teaching_task_id,
        candidate_index=candidate.candidate_index,
        assignments=candidate.assignments,
        template_signature=candidate.template_signature,
        score=candidate.score - fallback_penalty,
        room_rank_score=candidate.room_rank_score,
        teacher_profile_penalty=candidate.teacher_profile_penalty,
        metadata=metadata,
    )


def _renumber_candidate(candidate: TaskCandidate, index: int) -> TaskCandidate:
    return TaskCandidate(
        teaching_task_id=candidate.teaching_task_id,
        candidate_index=index,
        assignments=candidate.assignments,
        template_signature=candidate.template_signature,
        score=candidate.score,
        room_rank_score=candidate.room_rank_score,
        teacher_profile_penalty=candidate.teacher_profile_penalty,
        metadata=candidate.metadata,
    )
