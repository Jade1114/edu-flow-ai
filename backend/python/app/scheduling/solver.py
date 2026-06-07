"""CP-SAT global plan selector for V3 scheduling.

This layer chooses one prebuilt local plan for each teaching task. It does not
create resources or change plan templates; it only selects a globally compatible
combination and expands it into Java-ingestable scheme rows.
"""

from __future__ import annotations

from app.core.logging import service
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any



try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - exercised only without deps
    cp_model = None


DEFAULT_SCHEME_COUNT = 3
DEFAULT_TIME_LIMIT_SECONDS = 60.0
DEFAULT_SOLVER_WORKERS = 8
OBJECTIVE_SCALE = 1_000_000
MODEL_OBJECTIVE_WEIGHT = 1.0
TEACHER_PROFILE_OBJECTIVE_WEIGHT = 0.15
TEACHER_PROFILE_PENALTY_WEIGHT = 0.15

ResourceKey = tuple[str, int, int]
CoordKey = tuple[int, int, int]


@dataclass(frozen=True)
class CpSatPlanOption:
    task_index: int
    plan_index: int
    plan_id: str
    teaching_task_id: int
    teacher_id: int
    class_group_ids: tuple[int, ...]
    assignments: tuple[dict[str, Any], ...]
    resource_keys: tuple[ResourceKey, ...]
    hard_static: int
    quality_score: float
    teacher_profile_score: float
    teacher_profile_penalty: float
    teacher_profile_reasons: tuple[str, ...]


@dataclass(frozen=True)
class CpSatTaskPlans:
    row: dict[str, Any]
    options: tuple[CpSatPlanOption, ...]


def select_cp_sat_global_plans_jsonl(
    task_plans_path: str | Path,
    *,
    time_slot_id_by_coord: dict[CoordKey, int],
    scheme_count: int = DEFAULT_SCHEME_COUNT,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    solver_workers: int = DEFAULT_SOLVER_WORKERS,
    diversity_threshold: int | None = None,
    model_objective_weight: float = MODEL_OBJECTIVE_WEIGHT,
    teacher_profile_objective_weight: float = TEACHER_PROFILE_OBJECTIVE_WEIGHT,
    teacher_profile_penalty_weight: float = TEACHER_PROFILE_PENALTY_WEIGHT,
    summary_context: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Select globally compatible task plans and write schemes.jsonl.

    Raises ValueError when no feasible zero-conflict scheme can be produced.
    """

    if cp_model is None:
        raise RuntimeError("OR-Tools is not installed. Install ml/requirements.txt before running V3 CP-SAT.")

    started = time.perf_counter()
    source_path = Path(task_plans_path)
    tasks = load_cp_sat_task_plans(source_path, time_slot_id_by_coord=time_slot_id_by_coord)
    if not tasks:
        raise ValueError("task_plans.jsonl has no schedulable task plans")

    scheme_count = max(1, min(int(scheme_count), 20))
    time_limit_seconds = max(1.0, float(time_limit_seconds))
    solver_workers = max(1, int(solver_workers))
    diff_threshold = (
        max(8, int(len(tasks) * 0.02))
        if diversity_threshold is None
        else max(1, int(diversity_threshold))
    )

    out_dir = Path(output_dir) if output_dir else source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    schemes: list[dict[str, Any]] = []
    selected_solutions: list[set[tuple[int, int]]] = []
    statuses: list[str] = []
    objective_values: list[float] = []
    variable_count = 0
    constraint_count = 0

    for scheme_index in range(1, scheme_count + 1):
        solved = _solve_one_scheme(
            tasks,
            previous_solutions=selected_solutions,
            diversity_threshold=diff_threshold,
            time_limit_seconds=time_limit_seconds,
            solver_workers=solver_workers,
            model_objective_weight=model_objective_weight,
            teacher_profile_objective_weight=teacher_profile_objective_weight,
            teacher_profile_penalty_weight=teacher_profile_penalty_weight,
        )
        statuses.append(solved["solver_status"])
        objective_values.append(float(solved.get("objective_value") or 0.0))
        variable_count = max(variable_count, int(solved["variable_count"]))
        constraint_count = max(constraint_count, int(solved["constraint_count"]))
        if not solved["selected"]:
            break
        selected = set(solved["selected"])
        selected_solutions.append(selected)
        schemes.append(_scheme_to_json(scheme_index, selected, tasks))

    runtime_ms = round((time.perf_counter() - started) * 1000, 2)
    schemes_path = out_dir / "schemes.jsonl"
    summary_path = out_dir / "cp_sat_summary.json"
    final_status = statuses[-1] if statuses else "UNKNOWN"
    candidate_coverage_diagnosis = _candidate_coverage_diagnosis(
        solver_status=final_status,
        scheme_count=len(schemes),
        summary_context=summary_context,
    )
    summary = {
        "architecture": "v3_cp_sat_global_plan_selector",
        "source_path": str(source_path),
        "output_path": str(schemes_path),
        "summary_path": str(summary_path),
        "solver_status": final_status,
        "solver_statuses": statuses,
        "task_count": len(tasks),
        "scheme_count_requested": scheme_count,
        "scheme_count": len(schemes),
        "variable_count": variable_count,
        "constraint_count": constraint_count,
        "time_limit_seconds": time_limit_seconds,
        "solver_workers": solver_workers,
        "objective": "maximize_quality_plus_teacher_profile_v1",
        "objective_weights": {
            "model": model_objective_weight,
            "teacher_profile_score": teacher_profile_objective_weight,
            "teacher_profile_penalty": teacher_profile_penalty_weight,
        },
        "placement_top_k": (summary_context or {}).get("placement_top_k"),
        "raw_plan_count": (summary_context or {}).get("raw_plan_count"),
        "cp_plan_count": (summary_context or {}).get("cp_plan_count"),
        "plan_count": (summary_context or {}).get("plan_count"),
        "generation_mode": (summary_context or {}).get("generation_mode"),
        "preflight_no_candidate_task_count": (summary_context or {}).get("preflight_no_candidate_task_count"),
        "preflight_no_plan_task_count": (summary_context or {}).get("preflight_no_plan_task_count"),
        "preflight_estimated_feasible": (summary_context or {}).get("preflight_estimated_feasible"),
        "candidate_coverage_diagnosis": candidate_coverage_diagnosis,
        "objective_values": objective_values,
        "diversity_threshold": diff_threshold,
        "runtime_ms": runtime_ms,
        "schemes": [
            {
                "scheme_index": row["scheme_index"],
                "hard_conflicts": row["hard_conflicts"],
                "quality_score": row["quality_score"],
                "conflict_summary": row["conflict_summary"],
                "assignment_count": len(row["items"]),
            }
            for row in schemes
        ],
        "generated_at": _now_iso(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if not schemes:
        status = statuses[-1] if statuses else "UNKNOWN"
        diagnosis = ""
        if candidate_coverage_diagnosis:
            diagnosis = f"; diagnosis={candidate_coverage_diagnosis['message']}"
        raise ValueError(f"CP-SAT failed to find a feasible V3 scheme: status={status}; summary={summary_path}{diagnosis}")

    schemes_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in schemes),
        encoding="utf-8",
    )
    return summary


def _candidate_coverage_diagnosis(
    *,
    solver_status: str,
    scheme_count: int,
    summary_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    context = summary_context or {}
    no_candidate = int(context.get("preflight_no_candidate_task_count") or 0)
    no_plan = int(context.get("preflight_no_plan_task_count") or 0)
    if solver_status != "INFEASIBLE" or scheme_count > 0 or no_candidate > 0 or no_plan > 0:
        return None
    return {
        "type": "CANDIDATE_COVERAGE_INSUFFICIENT",
        "message": "CP-SAT INFEASIBLE but preflight has no no_candidate/no_plan tasks; likely candidate set coverage is too narrow or conflicts are concentrated.",
        "recommendation": "Increase placement_top_k/raw_plan_count and cp_plan_count, especially for first_feasible on 4000-level stress runs.",
        "placement_top_k": context.get("placement_top_k"),
        "raw_plan_count": context.get("raw_plan_count"),
        "cp_plan_count": context.get("cp_plan_count"),
    }


def load_cp_sat_task_plans(
    path: str | Path,
    *,
    time_slot_id_by_coord: dict[CoordKey, int],
) -> list[CpSatTaskPlans]:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"task plans file not found: {source_path}")

    tasks: list[CpSatTaskPlans] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for task_index, line in enumerate(handle):
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            if row.get("error"):
                continue
            options = tuple(
                option
                for plan_index, plan in enumerate(row.get("plans") or [])
                if (option := _plan_option(task_index, row, plan_index, plan, time_slot_id_by_coord=time_slot_id_by_coord))
                is not None
            )
            if options:
                tasks.append(CpSatTaskPlans(row=row, options=options))
    return tasks


def audit_scheme_items(items: list[dict[str, Any]]) -> dict[str, int]:
    teacher_counts: Counter[ResourceKey] = Counter()
    class_counts: Counter[ResourceKey] = Counter()
    room_counts: Counter[ResourceKey] = Counter()
    time_slot_mapping = 0
    for item in items:
        time_slot_id = int(item.get("time_slot_id") or 0)
        if time_slot_id <= 0:
            time_slot_mapping += 1
            continue
        teacher_id = int(item.get("teacher_id") or 0)
        if teacher_id > 0:
            teacher_counts[("teacher", teacher_id, time_slot_id)] += 1
        classroom_id = int(item.get("classroom_id") or 0)
        if classroom_id > 0:
            room_counts[("room", classroom_id, time_slot_id)] += 1
        for class_group_id in item.get("class_group_ids") or []:
            cid = int(class_group_id or 0)
            if cid > 0:
                class_counts[("class", cid, time_slot_id)] += 1

    return {
        "teacher": _duplicate_count(teacher_counts),
        "class": _duplicate_count(class_counts),
        "room": _duplicate_count(room_counts),
        "time_slot_mapping": time_slot_mapping,
        "hour_mismatch": 0,
    }


def _plan_option(
    task_index: int,
    row: dict[str, Any],
    plan_index: int,
    plan: dict[str, Any],
    *,
    time_slot_id_by_coord: dict[CoordKey, int],
) -> CpSatPlanOption | None:
    if not plan.get("valid", True):
        return None
    task = row.get("task") or {}
    teaching_task_id = int(row.get("teaching_task_id") or task.get("teaching_task_id") or 0)
    teacher_id = int(task.get("teacher_id") or 0)
    class_group_ids = tuple(int(value) for value in task.get("class_group_ids") or [] if int(value or 0) > 0)
    total_sessions = int(task.get("total_sessions") or 0)
    teacher_profile_score = float(plan.get("teacher_profile_score") or 1.0)
    teacher_profile_penalty = float(plan.get("teacher_profile_penalty") or 0.0)
    teacher_profile_reasons = tuple(str(value) for value in plan.get("teacher_profile_reasons") or [])

    assignments: list[dict[str, Any]] = []
    resource_keys: list[ResourceKey] = []
    for segment in plan.get("segments") or []:
        resource = segment.get("resource") or {}
        slot = resource.get("slot") or {}
        classroom = resource.get("classroom") or {}
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        classroom_id = int(classroom.get("id") or 0)
        for week in segment.get("weeks") or []:
            week_number = int(week)
            coord = (week_number, day, period)
            time_slot_id = time_slot_id_by_coord.get(coord)
            if time_slot_id is None:
                raise ValueError(f"plan {plan.get('plan_id')} uses unavailable time slot coord={coord}")
            assignment = {
                "teaching_task_id": teaching_task_id,
                "time_slot_id": int(time_slot_id),
                "classroom_id": classroom_id,
                "week_number": week_number,
                "day_of_week": day,
                "period_index": period,
                "teacher_id": teacher_id,
                "class_group_ids": list(class_group_ids),
                "classroom_name": classroom.get("name") or "",
                "selected_plan_id": plan.get("plan_id") or f"{teaching_task_id}_p{plan_index + 1:03d}",
                "template_id": segment.get("template_id") or "",
                "placement_score": round(float(resource.get("score") or 0.0), 6),
                "teacher_profile_score": round(teacher_profile_score, 6),
                "teacher_profile_penalty": round(teacher_profile_penalty, 6),
                "teacher_profile_reasons": list(teacher_profile_reasons),
            }
            assignments.append(assignment)
            if teacher_id > 0:
                resource_keys.append(("teacher", teacher_id, int(time_slot_id)))
            if classroom_id > 0:
                resource_keys.append(("room", classroom_id, int(time_slot_id)))
            for class_group_id in class_group_ids:
                resource_keys.append(("class", class_group_id, int(time_slot_id)))

    if len(assignments) != total_sessions or _has_internal_conflict(resource_keys):
        return None
    score = float(plan.get("score") or 0.0) * max(1, len(assignments))
    return CpSatPlanOption(
        task_index=task_index,
        plan_index=plan_index,
        plan_id=str(plan.get("plan_id") or f"{teaching_task_id}_p{plan_index + 1:03d}"),
        teaching_task_id=teaching_task_id,
        teacher_id=teacher_id,
        class_group_ids=class_group_ids,
        assignments=tuple(assignments),
        resource_keys=tuple(resource_keys),
        hard_static=0,
        quality_score=score,
        teacher_profile_score=teacher_profile_score,
        teacher_profile_penalty=teacher_profile_penalty,
        teacher_profile_reasons=teacher_profile_reasons,
    )


def _solve_one_scheme(
    tasks: list[CpSatTaskPlans],
    *,
    previous_solutions: list[set[tuple[int, int]]],
    diversity_threshold: int,
    time_limit_seconds: float,
    solver_workers: int,
    model_objective_weight: float,
    teacher_profile_objective_weight: float,
    teacher_profile_penalty_weight: float,
) -> dict[str, Any]:
    model = cp_model.CpModel()
    variables: dict[tuple[int, int], Any] = {}
    constraint_count = 0
    greedy_hint, greedy_conflicts = _greedy_plan_hint(tasks)

    for task in tasks:
        task_vars = []
        for option in task.options:
            var_key = (option.task_index, option.plan_index)
            var = model.NewBoolVar(f"x_{option.task_index}_{option.plan_index}")
            variables[var_key] = var
            task_vars.append(var)
        model.Add(sum(task_vars) == 1)
        constraint_count += 1

    resource_to_vars: dict[ResourceKey, list[Any]] = defaultdict(list)
    for task in tasks:
        for option in task.options:
            var = variables[(option.task_index, option.plan_index)]
            for key in set(option.resource_keys):
                resource_to_vars[key].append(var)
    for vars_for_resource in resource_to_vars.values():
        if len(vars_for_resource) > 1:
            model.AddAtMostOne(vars_for_resource)
            constraint_count += 1

    for previous in previous_solutions:
        previous_vars = [variables[key] for key in previous if key in variables]
        if previous_vars:
            model.Add(sum(previous_vars) <= max(0, len(previous_vars) - diversity_threshold))
            constraint_count += 1

    objective_terms = []
    for task in tasks:
        for option in task.options:
            var = variables[(option.task_index, option.plan_index)]
            objective_score = int(round(_objective_score(
                option,
                model_weight=model_objective_weight,
                teacher_profile_weight=teacher_profile_objective_weight,
                teacher_profile_penalty_weight=teacher_profile_penalty_weight,
            ) * OBJECTIVE_SCALE))
            objective_terms.append(objective_score * var)
    if objective_terms:
        model.Maximize(sum(objective_terms))

    for key, var in variables.items():
        model.AddHint(var, 1 if greedy_hint.get(key[0]) == key[1] else 0)

    ordered_vars = [
        variables[(option.task_index, option.plan_index)]
        for task in _tasks_by_search_priority(tasks)
        for option in sorted(task.options, key=lambda item: (item.plan_index != greedy_hint.get(item.task_index), item.plan_index))
        if (option.task_index, option.plan_index) in variables
    ]
    if ordered_vars:
        model.AddDecisionStrategy(ordered_vars, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = solver_workers
    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    solver.parameters.log_search_progress = True
    cp_sat_log_dir = Path(__file__).resolve().parents[3] / "logs"
    cp_sat_log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["GLOG_log_dir"] = str(cp_sat_log_dir)

    service.info("[CP-SAT] 求解启动: variables=%d, constraints=%d, workers=%d, time_limit=%.0fs",
                 len(variables), constraint_count, solver_workers, time_limit_seconds)
    service.info("[CP-SAT] 搜索日志 → %s/ 目录 (GLOG 格式)", cp_sat_log_dir)
    _solve_started = time.time()
    status = solver.Solve(model)
    _solve_elapsed = time.time() - _solve_started
    service.info("[CP-SAT] 求解结束: status=%s, elapsed=%.0fs", solver.StatusName(status), _solve_elapsed)
    status_name = solver.StatusName(status)
    selected: list[tuple[int, int]] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for key, var in variables.items():
            if solver.BooleanValue(var):
                selected.append(key)
    return {
        "solver_status": status_name,
        "selected": selected,
        "variable_count": len(variables),
        "constraint_count": constraint_count,
        "objective_value": round(solver.ObjectiveValue() / OBJECTIVE_SCALE, 6) if selected else 0.0,
        "greedy_initial_conflicts": greedy_conflicts,
    }


def _objective_score(
    option: CpSatPlanOption,
    *,
    model_weight: float = MODEL_OBJECTIVE_WEIGHT,
    teacher_profile_weight: float = TEACHER_PROFILE_OBJECTIVE_WEIGHT,
    teacher_profile_penalty_weight: float = TEACHER_PROFILE_PENALTY_WEIGHT,
) -> float:
    session_count = max(1, len(option.assignments))
    model_score = max(0.0, option.quality_score) * max(0.0, model_weight)
    profile_score = max(0.0, option.teacher_profile_score) * session_count * max(0.0, teacher_profile_weight)
    profile_penalty = max(0.0, option.teacher_profile_penalty) * session_count * max(0.0, teacher_profile_penalty_weight)
    return model_score + profile_score - profile_penalty


def _greedy_plan_hint(tasks: list[CpSatTaskPlans]) -> tuple[dict[int, int], int]:
    counts: Counter[ResourceKey] = Counter()
    selected: dict[int, int] = {}
    for task in _tasks_by_search_priority(tasks):
        option = min(
            task.options,
            key=lambda item: (
                _option_overlap(item, counts),
                -item.quality_score,
                item.plan_index,
            ),
        )
        selected[option.task_index] = option.plan_index
        counts.update(set(option.resource_keys))
    conflicts = sum(count - 1 for count in counts.values() if count > 1)
    return selected, conflicts


def _tasks_by_search_priority(tasks: list[CpSatTaskPlans]) -> list[CpSatTaskPlans]:
    teacher_load: Counter[int] = Counter()
    for task in tasks:
        if task.options:
            option = task.options[0]
            teacher_load[option.teacher_id] += len(option.assignments)

    def key(task: CpSatTaskPlans) -> tuple[int, int, int]:
        resource_keys: set[ResourceKey] = set()
        for option in task.options:
            resource_keys.update(option.resource_keys)
        first = task.options[0]
        return (len(resource_keys), -teacher_load[first.teacher_id], -len(first.assignments))

    return sorted(tasks, key=key)


def _option_overlap(option: CpSatPlanOption, counts: Counter[ResourceKey]) -> int:
    return sum(counts.get(key, 0) for key in set(option.resource_keys))


def _scheme_to_json(scheme_index: int, selected: set[tuple[int, int]], tasks: list[CpSatTaskPlans]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    quality_score = 0.0
    by_key = {
        (option.task_index, option.plan_index): option
        for task in tasks
        for option in task.options
    }
    for key in sorted(selected):
        option = by_key[key]
        items.extend(dict(item) for item in option.assignments)
        quality_score += option.quality_score
    items.sort(key=lambda item: (
        int(item.get("teaching_task_id") or 0),
        int(item.get("time_slot_id") or 0),
        int(item.get("classroom_id") or 0),
    ))
    conflicts = audit_scheme_items(items)
    return {
        "scheme_index": scheme_index,
        "items": items,
        "hard_conflicts": sum(conflicts.values()),
        "quality_score": round(quality_score, 6),
        "conflict_summary": conflicts,
        "assignment_count": len(items),
        "chromosome": [key[1] for key in sorted(selected)],
    }


def _atomic_session_fallback_scheme(
    scheme_index: int,
    tasks: list[CpSatTaskPlans],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    teacher_load: Counter[int] = Counter()
    class_load: Counter[int] = Counter()
    expected_assignment_count = 0
    for task in tasks:
        first = task.options[0]
        expected_assignment_count += len(first.assignments)
        teacher_load[first.teacher_id] += len(first.assignments)
        for class_group_id in first.class_group_ids:
            class_load[class_group_id] += len(first.assignments)

    used: set[ResourceKey] = set()
    items: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    class_week_load: Counter[tuple[int, int]] = Counter()
    teacher_week_load: Counter[tuple[int, int]] = Counter()
    global_week_load: Counter[int] = Counter()
    for task in sorted(tasks, key=lambda item: _atomic_task_priority(item, teacher_load, class_load)):
        first = task.options[0]
        required_count = len(first.assignments)
        atoms = _atomic_candidates(task)
        selected: list[dict[str, Any]] = []
        local_slots: set[tuple[int, int, int]] = set()
        while len(selected) < required_count:
            best_assignment: dict[str, Any] | None = None
            best_key: tuple[float, ...] | None = None
            for assignment in _first_feasible_atom_per_week(atoms, used=used, local_slots=local_slots):
                candidate_key = _atomic_assignment_balance_key(
                    assignment,
                    class_week_load=class_week_load,
                    teacher_week_load=teacher_week_load,
                    global_week_load=global_week_load,
                    selected=selected,
                )
                if best_key is None or candidate_key < best_key:
                    best_key = candidate_key
                    best_assignment = assignment
            if best_assignment is None:
                break
            assignment = dict(best_assignment)
            local_key = (
                int(assignment.get("week_number") or 0),
                int(assignment.get("day_of_week") or 0),
                int(assignment.get("period_index") or 0),
            )
            resource_keys = _assignment_resource_keys(assignment)
            selected.append(assignment)
            local_slots.add(local_key)
            used.update(resource_keys)
            _reserve_atomic_balance_load(
                assignment,
                class_week_load=class_week_load,
                teacher_week_load=teacher_week_load,
                global_week_load=global_week_load,
            )
        if len(selected) < required_count:
            failed.append({
                "teaching_task_id": first.teaching_task_id,
                "teacher_id": first.teacher_id,
                "required_count": required_count,
                "selected_count": len(selected),
                "candidate_count": len(atoms),
            })
            continue
        items.extend(selected)

    items.sort(key=lambda item: (
        int(item.get("teaching_task_id") or 0),
        int(item.get("time_slot_id") or 0),
        int(item.get("classroom_id") or 0),
    ))
    conflicts = audit_scheme_items(items)
    summary = {
        "mode": "atomic_session_fallback",
        "task_count": len(tasks),
        "failed_task_count": len(failed),
        "assignment_count": len(items),
        "expected_assignment_count": expected_assignment_count,
        "conflict_summary": conflicts,
        "week_distribution": _week_distribution(items),
        "failed_tasks": failed[:20],
    }
    if failed or sum(conflicts.values()) > 0 or len(items) != expected_assignment_count:
        return None, summary
    quality_score = sum(float(item.get("placement_score") or 0.0) for item in items)
    return {
        "scheme_index": scheme_index,
        "items": items,
        "hard_conflicts": 0,
        "quality_score": round(quality_score, 6),
        "conflict_summary": conflicts,
        "assignment_count": len(items),
        "chromosome": [],
        "selector_mode": "atomic_session_fallback",
    }, summary


def _atomic_task_priority(
    task: CpSatTaskPlans,
    teacher_load: Counter[int],
    class_load: Counter[int],
) -> tuple[int, int, int, int]:
    first = task.options[0]
    candidate_count = len(_atomic_candidates(task))
    max_class_load = max((class_load[class_group_id] for class_group_id in first.class_group_ids), default=0)
    return (candidate_count, -teacher_load[first.teacher_id], -max_class_load, -len(first.assignments))


def _first_feasible_atom_per_week(
    atoms: list[dict[str, Any]],
    *,
    used: set[ResourceKey],
    local_slots: set[tuple[int, int, int]],
) -> list[dict[str, Any]]:
    by_week: dict[int, dict[str, Any]] = {}
    for assignment in atoms:
        week = int(assignment.get("week_number") or 0)
        if week in by_week:
            continue
        local_key = (
            week,
            int(assignment.get("day_of_week") or 0),
            int(assignment.get("period_index") or 0),
        )
        if local_key in local_slots:
            continue
        resource_keys = _assignment_resource_keys(assignment)
        if any(key in used for key in resource_keys):
            continue
        by_week[week] = assignment
        if len(by_week) >= 18:
            break
    return list(by_week.values())


def _atomic_candidates(task: CpSatTaskPlans) -> list[dict[str, Any]]:
    seen: set[tuple[int, int]] = set()
    atoms: list[dict[str, Any]] = []
    for option in sorted(task.options, key=lambda item: (-item.quality_score, item.plan_index)):
        for assignment in option.assignments:
            key = (int(assignment.get("time_slot_id") or 0), int(assignment.get("classroom_id") or 0))
            if key in seen:
                continue
            seen.add(key)
            atoms.append(dict(assignment))
    atoms.sort(key=lambda item: (
        -float(item.get("placement_score") or 0.0),
        int(item.get("week_number") or 0),
        int(item.get("day_of_week") or 0),
        int(item.get("period_index") or 0),
        int(item.get("classroom_id") or 0),
    ))
    return atoms


def _atomic_assignment_balance_key(
    assignment: dict[str, Any],
    *,
    class_week_load: Counter[tuple[int, int]],
    teacher_week_load: Counter[tuple[int, int]],
    global_week_load: Counter[int],
    selected: list[dict[str, Any]],
) -> tuple[float, ...]:
    week = int(assignment.get("week_number") or 0)
    teacher_id = int(assignment.get("teacher_id") or 0)
    class_group_ids = [int(value or 0) for value in assignment.get("class_group_ids") or [] if int(value or 0) > 0]
    class_load = max((class_week_load[(class_group_id, week)] for class_group_id in class_group_ids), default=0)
    selected_week_count = sum(1 for item in selected if int(item.get("week_number") or 0) == week)
    return (
        _academic_week_penalty(week) + class_load * 8.0 + selected_week_count * 4.0,
        teacher_week_load[(teacher_id, week)] * 3.0 if teacher_id > 0 else 0.0,
        global_week_load[week] * 0.001,
        -float(assignment.get("placement_score") or 0.0),
        int(assignment.get("day_of_week") or 0),
        int(assignment.get("period_index") or 0),
        int(assignment.get("classroom_id") or 0),
    )


def _academic_week_penalty(week: int) -> float:
    if week <= 0:
        return 100.0
    if 2 <= week <= 16:
        midpoint = 8.5
        return abs(week - midpoint) * 0.02
    if week == 1:
        return 4.0
    return 2.5 + max(0, week - 16) * 0.75


def _reserve_atomic_balance_load(
    assignment: dict[str, Any],
    *,
    class_week_load: Counter[tuple[int, int]],
    teacher_week_load: Counter[tuple[int, int]],
    global_week_load: Counter[int],
) -> None:
    week = int(assignment.get("week_number") or 0)
    teacher_id = int(assignment.get("teacher_id") or 0)
    if teacher_id > 0:
        teacher_week_load[(teacher_id, week)] += 1
    for value in assignment.get("class_group_ids") or []:
        class_group_id = int(value or 0)
        if class_group_id > 0:
            class_week_load[(class_group_id, week)] += 1
    if week > 0:
        global_week_load[week] += 1


def _week_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[int] = Counter(int(item.get("week_number") or 0) for item in items)
    return {str(week): counts[week] for week in sorted(counts) if week > 0}


def _assignment_resource_keys(assignment: dict[str, Any]) -> tuple[ResourceKey, ...]:
    keys: list[ResourceKey] = []
    time_slot_id = int(assignment.get("time_slot_id") or 0)
    teacher_id = int(assignment.get("teacher_id") or 0)
    classroom_id = int(assignment.get("classroom_id") or 0)
    if teacher_id > 0:
        keys.append(("teacher", teacher_id, time_slot_id))
    if classroom_id > 0:
        keys.append(("room", classroom_id, time_slot_id))
    for class_group_id in assignment.get("class_group_ids") or []:
        cid = int(class_group_id or 0)
        if cid > 0:
            keys.append(("class", cid, time_slot_id))
    return tuple(keys)


def _duplicate_count(counter: Counter[ResourceKey]) -> int:
    return sum(max(0, count - 1) for count in counter.values())


def _has_internal_conflict(resource_keys: list[ResourceKey]) -> bool:
    counts: Counter[ResourceKey] = Counter(resource_keys)
    return any(count > 1 for count in counts.values())


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
