"""Pipeline entrypoint for candidate-pool guided GA generation."""

from __future__ import annotations

import logging
import os
import random
import time
from collections import defaultdict
from typing import Any

from ml.ga_config import resolve_ga_params
from ml.scheduling.teacher_profiles import load_teacher_profiles_jsonl
from ml.scheduling_v2.candidate_pool import build_candidate_pool
from ml.scheduling_v2.data_loader import load_context, resolve_scheme_count
from ml.scheduling_v2.exporter import write_output
from ml.scheduling_v2.ga_solver import solve

_log = logging.getLogger("ga")


def run_generation(task_id: int, teacher_profiles_jsonl: str | None = None) -> dict[str, Any]:
    profile_path = teacher_profiles_jsonl or os.environ.get("TEACHER_PROFILES_JSONL")
    teacher_profiles = load_teacher_profiles_jsonl(profile_path) if profile_path else None
    context = load_context(task_id, teacher_profiles)
    validate_hard_feasibility(context)

    ga_params = resolve_ga_params(_log)
    scheme_count = resolve_scheme_count(context.raw_config)
    pool_size = int(ga_params.get("candidate_pool_size") or 500)
    candidate_top_n = int(ga_params.get("candidate_top_n") or 40)
    candidate_workers = int(ga_params.get("candidate_workers") or 1)

    _log.info(
        "Candidate-pool GA start: task_id=%s tasks=%s scheme_count=%s pool_size=%s candidate_workers=%s",
        task_id,
        len(context.tasks),
        scheme_count,
        pool_size,
        candidate_workers,
    )
    pool_started_at = time.perf_counter()
    pools = build_candidate_pool(
        context,
        pool_size_per_task=pool_size,
        room_top_n=max(8, min(40, candidate_top_n // 2)),
        template_top_n=max(4, min(16, candidate_top_n // 2)),
        slot_top_n=max(16, min(80, candidate_top_n)),
        candidate_workers=candidate_workers,
        local_expand_enabled=bool(ga_params.get("candidate_local_expand_enabled", True)),
        local_expand_slot_limit=int(ga_params.get("candidate_local_expand_slot_limit", 12)),
        local_expand_room_limit=int(ga_params.get("candidate_local_expand_room_limit", 12)),
        local_expand_max_added_per_task=int(ga_params.get("candidate_local_expand_max_added_per_task", 80)),
    )
    candidate_pool_elapsed_ms = (time.perf_counter() - pool_started_at) * 1000

    rng = random.Random((task_id * 1_000_003 + 97) % 2_147_483_647)
    schemes = solve(
        context,
        pools,
        scheme_count=scheme_count,
        population_size=int(ga_params["population_size"]),
        generations=int(ga_params["generations"]),
        elite_size=int(ga_params["elite_size"]),
        tournament_size=int(ga_params["tournament_size"]),
        mutation_rate=float(ga_params["mutation_rate"]),
        repair_max_tasks=int(ga_params.get("repair_max_tasks") or 0),
        repair_candidate_limit=int(ga_params.get("repair_candidate_limit") or 12),
        greedy_init_scan_limit=int(ga_params.get("greedy_init_scan_limit", 8)),
        greedy_init_variants=int(ga_params.get("greedy_init_variants", 2)),
        directed_mutation_scan_limit=int(ga_params.get("directed_mutation_scan_limit", 0)),
        local_repair_enabled=bool(ga_params.get("local_repair_enabled", True)),
        local_repair_candidate_limit=int(ga_params.get("local_repair_candidate_limit", 12)),
        local_mutation_enabled=bool(ga_params.get("local_mutation_enabled", True)),
        local_mutation_candidate_limit=int(ga_params.get("local_mutation_candidate_limit", 8)),
        rng=rng,
    )
    result = write_output(
        context,
        schemes,
        pools,
        candidate_pool_stats={
            "candidate_workers": candidate_workers,
            "candidate_pool_elapsed_ms": candidate_pool_elapsed_ms,
        },
    )
    _log.info("Candidate-pool GA done: task_id=%s output_dir=%s", task_id, result["output_dir"])
    return result


def validate_hard_feasibility(context) -> None:
    """Reject timetable requests that exceed one resource's hard time capacity."""

    allowed_slot_count = len(context.allowed_time_slot_ids)
    if allowed_slot_count <= 0:
        raise ValueError("排课失败：生成配置过滤后没有可用时间段")

    teacher_load: dict[int, int] = defaultdict(int)
    teacher_names: dict[int, str] = {}
    class_load: dict[int, int] = defaultdict(int)
    for task in context.tasks:
        teacher_load[task.teacher_id] += task.total_lessons
        teacher_names[task.teacher_id] = task.teacher_name
        for class_group_id in task.class_group_ids:
            class_load[class_group_id] += task.total_lessons

    overloaded_teachers = [
        (load, teacher_id, teacher_names.get(teacher_id) or "")
        for teacher_id, load in teacher_load.items()
        if load > allowed_slot_count
    ]
    overloaded_classes = [
        (load, class_group_id)
        for class_group_id, load in class_load.items()
        if load > allowed_slot_count
    ]
    if not overloaded_teachers and not overloaded_classes:
        return

    details: list[str] = []
    if overloaded_teachers:
        overloaded_teachers.sort(reverse=True)
        details.append(
            "教师超容量：" + "；".join(
                f"{name or teacher_id}({teacher_id}) 需{load}片段"
                for load, teacher_id, name in overloaded_teachers[:5]
            )
        )
    if overloaded_classes:
        overloaded_classes.sort(reverse=True)
        details.append(
            "班级超容量：" + "；".join(
                f"{class_group_id} 需{load}片段"
                for load, class_group_id in overloaded_classes[:5]
            )
        )
    raise ValueError(
        "排课失败：当前任务集在硬约束下不可行，"
        f"允许时间片只有 {allowed_slot_count} 个；"
        + "；".join(details)
        + "。请缩小 allocation_task 绑定范围、拆分超载教师任务，或扩展允许周次/星期/节次后重试。"
    )
