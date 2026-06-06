"""V3 scheduling pipeline orchestrator.

Full pipeline for professional courses only (no public courses):
  1. Fetch teaching tasks from DB
  2. Placement Model → TopK resources per task (parallel)
  3. Template Generator → week distribution plans per task (parallel)
  4. CP-SAT Global Plan Selector → choose one plan per task
  5. Write final schedule JSONL
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    ensure_default_time_slots,
    fetch_allocation_task,
    fetch_all,
    fetch_generation_config,
    fetch_time_slots,
)
from ml.scheduling_v3.cp_sat_selector import (
    DEFAULT_TIME_LIMIT_SECONDS,
    MODEL_OBJECTIVE_WEIGHT,
    TEACHER_PROFILE_OBJECTIVE_WEIGHT,
    TEACHER_PROFILE_PENALTY_WEIGHT,
    audit_scheme_items,
    select_cp_sat_global_plans_jsonl,
)
from ml.scheduling_v3.placement_direct import DirectPlacementModel
from ml.scheduling_v3.plan_templates import (
    _build_task_plan_row,
    _load_teacher_profiles,
    _read_candidate_rows,
    WeekUsageAllocator,
)

DEFAULT_TOP_K = 50
MAX_TOP_K = 200
MAX_PLAN_COUNT = 500
DEFAULT_PLAN_COUNT = 120
DEFAULT_CP_PLAN_COUNT = 40
MAX_SOLVER_TIME_LIMIT_SECONDS = 3600.0
DEFAULT_GENERATION_MODE = "AUTO"
DEFAULT_SINGLE_GENERATION_MODE = "QUALITY"
FEASIBILITY_MODES = {"FEASIBILITY", "FIRST_SOLUTION", "FIRST_FEASIBLE"}
AUTO_GENERATION_MODES = {"AUTO", "AUTOMATIC", "PIPELINE"}
AUTO_STAGE_ORDER = ("FIRST_FEASIBLE", "QUALITY_OPTIMIZATION", "DIVERSITY_SEARCH")
DEFAULT_SEMESTER_WEEKS = 18
DEFAULT_ALLOWED_WEEKS = set(range(1, DEFAULT_SEMESTER_WEEKS + 1))
DEFAULT_ALLOWED_WEEKDAYS = set(range(1, 6))
DEFAULT_ALLOWED_PERIODS = set(range(1, 6))
LARGE_STRESS_TASK_THRESHOLD = 4000
FIRST_FEASIBLE_MIN_TOP_K = 64
FIRST_FEASIBLE_MIN_PLAN_COUNT = 64
FIRST_FEASIBLE_MIN_CP_PLAN_COUNT = 16
DEFAULT_STAGE_SOLVER_WORKERS = {
    "FIRST_FEASIBLE": 4,
    "QUALITY_OPTIMIZATION": 8,
    "DIVERSITY_SEARCH": 8,
}
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "data" / "generated" / "v3"


def run_v3_pipeline(
    allocation_task_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    plan_count: int = DEFAULT_PLAN_COUNT,
    scheme_count: int | None = None,
    solver_time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    solver_workers: int | None = None,
    generation_mode: str | None = None,
    max_auto_stage: str | None = None,
    skip_diversity: bool = False,
    output_dir: Path | str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one V3 scheduling mode for professional courses.

    Returns a summary dict with paths and statistics.
    """
    if _is_auto_generation_mode(generation_mode):
        return run_v3_auto_pipeline(
            allocation_task_id,
            top_k=top_k,
            plan_count=plan_count,
            scheme_count=scheme_count,
            solver_time_limit_seconds=solver_time_limit_seconds,
            solver_workers=solver_workers,
            max_auto_stage=max_auto_stage,
            skip_diversity=skip_diversity,
            requested_generation_mode=generation_mode,
            output_dir=output_dir,
            progress_callback=progress_callback,
        )

    started = time.perf_counter()

    def emit(stage: str, message: str, progress: int, **extra: Any) -> None:
        if progress_callback is None:
            return
        payload = {"stage": stage, "message": message, "progress": progress, **extra}
        progress_callback(payload)

    emit("PREFLIGHT", "初始化 V3 排课流水线...", 5)
    out_dir = _resolve_output_dir(allocation_task_id, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Load data from DB ───────────────────────────────────
    emit("PREFLIGHT", "加载排课任务、资源和生成配置...", 8)
    print("[V3] Step 1: Loading data from DB...")
    db = load_db_config()
    conn = connect(db)
    try:
        allocation_task = fetch_allocation_task(conn, allocation_task_id)
        if not allocation_task:
            raise ValueError(f"Allocation task {allocation_task_id} not found")
        raw_config = fetch_generation_config(conn, allocation_task_id)
        time_slots = fetch_time_slots(conn)
        seeded_time_slots = 0
        if not time_slots:
            seeded_time_slots = ensure_default_time_slots(conn)
            time_slots = fetch_time_slots(conn)
        filtered_time_slots = _filter_time_slots(time_slots, raw_config)
        if not filtered_time_slots:
            raise ValueError(
                "排课失败：生成配置过滤后没有可用时间段，"
                f"time_slot_count={len(time_slots)}, raw_config={raw_config}"
            )
        time_slot_id_by_coord = _time_slot_id_by_coord(filtered_time_slots)
        resolved_generation_mode = _resolve_generation_mode(raw_config, generation_mode)
        resolved_scheme_count = scheme_count if scheme_count is not None else _resolve_scheme_count(raw_config)
        if resolved_generation_mode in FEASIBILITY_MODES:
            resolved_scheme_count = 1
        resolved_top_k = _resolve_bounded_int(raw_config, "placement_top_k", top_k, 1, MAX_TOP_K)
        resolved_plan_count = _resolve_plan_count(raw_config, plan_count)
        resolved_cp_plan_count = _resolve_bounded_int(raw_config, "cp_plan_count", DEFAULT_CP_PLAN_COUNT, 1, MAX_PLAN_COUNT)
        resolved_solver_time_limit = _resolve_solver_time_limit(raw_config, solver_time_limit_seconds)

        teaching_tasks = list(fetch_all(conn,
            """SELECT tt.*, c.code AS course_code, c.name AS course_name,
                      c.course_type, c.required_room_type,
                      t.name AS teacher_name, t.department AS teacher_department
               FROM teaching_task tt
               JOIN allocation_task_teaching_task att ON tt.id = att.teaching_task_id
               JOIN course c ON tt.course_id = c.id
               JOIN teacher t ON tt.primary_teacher_id = t.id
               WHERE att.allocation_task_id = %s""",
            (allocation_task_id,)))
        courses = {c["code"]: c for c in fetch_all(conn, "SELECT * FROM course")}
        classrooms = {c["name"]: c for c in fetch_all(conn, "SELECT * FROM classroom")}
        # Add synthetic IDs for classrooms that don't have them
        for name, room in classrooms.items():
            if not room.get("id"):
                room["id"] = hash(name) % 100000 + 1
        class_groups = {c["name"]: c for c in fetch_all(conn, "SELECT * FROM class_group")}
        teachers = {t["name"]: t for t in fetch_all(conn, "SELECT * FROM teacher")}

        # Load task → class_group mapping
        task_cg_map: dict[int, str] = {}
        cg_rows = fetch_all(conn,
            """SELECT ttcg.teaching_task_id, cg.name AS class_group_name
               FROM teaching_task_class_group ttcg
               JOIN class_group cg ON ttcg.class_group_id = cg.id
               JOIN allocation_task_teaching_task att ON ttcg.teaching_task_id = att.teaching_task_id
               WHERE att.allocation_task_id = %s""",
            (allocation_task_id,))
        for row in cg_rows:
            task_cg_map[row["teaching_task_id"]] = row["class_group_name"]
    finally:
        conn.close()

    resolved_top_k, resolved_plan_count, resolved_cp_plan_count = _widen_first_feasible_candidates(
        task_count=len(teaching_tasks),
        generation_mode=resolved_generation_mode,
        placement_top_k=resolved_top_k,
        raw_plan_count=resolved_plan_count,
        cp_plan_count=resolved_cp_plan_count,
    )

    print(f"  Tasks: {len(teaching_tasks)}, Courses: {len(courses)}, "
          f"Classrooms: {len(classrooms)}, Classes: {len(class_groups)}, "
          f"Teachers: {len(teachers)}, TimeSlots: {len(time_slot_id_by_coord)}, "
          f"Schemes: {resolved_scheme_count}, TopK: {resolved_top_k}, "
          f"Plans: {resolved_plan_count}, CpPlans: {resolved_cp_plan_count}, "
          f"SolverLimit: {resolved_solver_time_limit}s, Mode: {resolved_generation_mode}, "
          f"SeededTimeSlots: {seeded_time_slots}")

    # ── Step 2: Placement Model inference ───────────────────────────
    emit("PREFLIGHT", "Placement Model 正在生成资源候选...", 18, task_count=len(teaching_tasks), top_k=resolved_top_k)
    print("[V3] Step 2: Placement Model inference...")
    model = DirectPlacementModel.load()
    candidates_path = out_dir / "placement_candidates.jsonl"
    task_count = _run_placement_inference(
        teaching_tasks=teaching_tasks,
        task_cg_map=task_cg_map,
        courses=courses,
        classrooms=classrooms,
        class_groups=class_groups,
        teachers=teachers,
        model=model,
        top_k=resolved_top_k,
        output_path=candidates_path,
        allocation_task_id=allocation_task_id,
        raw_config=raw_config,
    )
    print(f"  {task_count} tasks → {candidates_path}")

    # ── Step 3: Template generation ─────────────────────────────────
    emit("PREFLIGHT", "正在生成 task plans，用于 CP-SAT 全局选择...", 32, raw_plan_count=resolved_plan_count)
    print("[V3] Step 3: Template generation...")
    task_plans_path = out_dir / "task_plans.jsonl"
    task_plans_count = _run_template_generation_parallel(
        candidates_path=str(candidates_path),
        output_path=task_plans_path,
        plan_count=resolved_plan_count,
    )
    print(f"  {task_plans_count} tasks → {task_plans_path}")

    preflight_summary = _write_preflight_report(
        task_plans_path,
        out_dir,
        expected_task_count=len(teaching_tasks),
        placement_top_k=resolved_top_k,
        raw_plan_count=resolved_plan_count,
        cp_plan_count=resolved_cp_plan_count,
        generation_mode=resolved_generation_mode,
    )
    print(
        "  Preflight: "
        f"tasks={preflight_summary['task_count']} "
        f"no_plan={preflight_summary['no_plan_task_count']} "
        f"estimated_feasible={preflight_summary['estimated_feasible']}"
    )
    emit(
        "PREFLIGHT",
        "Preflight 诊断完成，准备判断是否进入 CP-SAT...",
        45,
        report_path=preflight_summary.get("report_path"),
        no_candidate_task_count=preflight_summary.get("no_candidate_task_count"),
        no_plan_task_count=preflight_summary.get("no_plan_task_count"),
        estimated_feasible=preflight_summary.get("estimated_feasible"),
    )
    if preflight_summary["no_plan_task_count"] > 0 or preflight_summary["no_candidate_task_count"] > 0:
        report_path = preflight_summary["report_path"]
        raise ValueError(
            "V3 preflight failed: "
            f"no_candidate_task_count={preflight_summary['no_candidate_task_count']}, "
            f"no_plan_task_count={preflight_summary['no_plan_task_count']}; "
            f"report={report_path}"
        )
    cp_task_plans_path = out_dir / "task_plans_cp.jsonl"
    _write_cp_task_plans(task_plans_path, cp_task_plans_path, resolved_cp_plan_count)

    # ── Step 4: CP-SAT global plan selection ─────────────────────────
    cp_stage = "FIRST_FEASIBLE" if resolved_generation_mode in FEASIBILITY_MODES else "QUALITY_OPTIMIZATION"
    if resolved_scheme_count > 1:
        cp_stage = "DIVERSITY_SEARCH"
    resolved_solver_workers = _resolve_solver_workers(solver_workers, cp_stage)
    stage_strategy = _stage_strategy(
        cp_stage,
        workers=resolved_solver_workers,
        time_limit=resolved_solver_time_limit,
        top_k=resolved_top_k,
        raw_plan_count=resolved_plan_count,
        cp_plan_count=resolved_cp_plan_count,
        scheme_count=resolved_scheme_count,
        objective_mode=resolved_generation_mode,
    )
    emit(
        cp_stage,
        "CP-SAT 正在做全局无冲突方案选择...",
        55,
        scheme_count=resolved_scheme_count,
        stage_strategy=stage_strategy,
        strategy=_format_stage_strategy(stage_strategy),
    )
    print("[V3] Step 4: CP-SAT global plan selection...")
    objective_weights = _resolve_cp_sat_objective_weights(raw_config)
    if resolved_generation_mode in FEASIBILITY_MODES:
        objective_weights["teacher_profile_score"] = 0.0
        objective_weights["teacher_profile_penalty"] = 0.0
    cp_sat_summary = select_cp_sat_global_plans_jsonl(
        cp_task_plans_path,
        time_slot_id_by_coord=time_slot_id_by_coord,
        scheme_count=resolved_scheme_count,
        time_limit_seconds=resolved_solver_time_limit,
        solver_workers=resolved_solver_workers,
        model_objective_weight=objective_weights["model"],
        teacher_profile_objective_weight=objective_weights["teacher_profile_score"],
        teacher_profile_penalty_weight=objective_weights["teacher_profile_penalty"],
        summary_context={
            "placement_top_k": resolved_top_k,
            "raw_plan_count": resolved_plan_count,
            "cp_plan_count": resolved_cp_plan_count,
            "plan_count": resolved_plan_count,
            "generation_mode": resolved_generation_mode,
            "preflight_no_candidate_task_count": preflight_summary.get("no_candidate_task_count"),
            "preflight_no_plan_task_count": preflight_summary.get("no_plan_task_count"),
            "preflight_estimated_feasible": preflight_summary.get("estimated_feasible"),
        },
        output_dir=out_dir,
    )
    schemes_path = Path(cp_sat_summary["output_path"])
    conflicts_after = _audit_schemes_jsonl(schemes_path)
    print(f"  Schemes: {cp_sat_summary['scheme_count']}/{resolved_scheme_count}; "
          f"Conflicts after: {conflicts_after}")
    emit(
        "PERSISTING",
        "CP-SAT 已产出方案，准备交给后端入库和冲突检测...",
        68,
        scheme_count=cp_sat_summary.get("scheme_count"),
        solver_status=cp_sat_summary.get("solver_status"),
        summary_path=cp_sat_summary.get("summary_path"),
        stage_strategy=stage_strategy,
        strategy=_format_stage_strategy(stage_strategy),
    )

    runtime_s = round(time.perf_counter() - started, 2)
    summary = {
        "architecture": "v3_cp_sat_global_plan_selector",
        "allocation_task_id": allocation_task_id,
        "output_dir": str(out_dir),
        "schemes_path": str(schemes_path),
        "candidates_path": str(candidates_path),
        "task_plans_path": str(task_plans_path),
        "cp_task_plans_path": str(cp_task_plans_path),
        "preflight_summary_path": preflight_summary.get("summary_path"),
        "preflight_report_path": preflight_summary.get("report_path"),
        "preflight": preflight_summary,
        "cp_sat_summary_path": cp_sat_summary.get("summary_path"),
        "task_count": len(teaching_tasks),
        "assigned_count": cp_sat_summary.get("task_count"),
        "placement_top_k": resolved_top_k,
        "raw_plan_count": resolved_plan_count,
        "cp_plan_count": resolved_cp_plan_count,
        "solver_time_limit_seconds": resolved_solver_time_limit,
        "solver_workers": resolved_solver_workers,
        "stage_strategy": stage_strategy,
        "generation_mode": resolved_generation_mode,
        "plan_count": resolved_plan_count,
        "scheme_count": cp_sat_summary.get("scheme_count"),
        "scheme_count_requested": resolved_scheme_count,
        "solver_status": cp_sat_summary.get("solver_status"),
        "objective": cp_sat_summary.get("objective"),
        "objective_weights": cp_sat_summary.get("objective_weights"),
        "seeded_time_slots": seeded_time_slots,
        "conflicts": conflicts_after,
        "runtime_s": runtime_s,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    summary_path = out_dir / "v3_summary.json"
    summary["summary_path"] = str(summary_path)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    emit(
        "DONE",
        "V3 排课流水线完成，后端正在读取方案结果...",
        70,
        output_dir=str(out_dir),
        schemes_path=str(schemes_path),
        runtime_s=runtime_s,
        stage_strategy=stage_strategy,
        strategy=_format_stage_strategy(stage_strategy),
    )
    print(f"[V3] Done in {runtime_s}s. Conflicts: {conflicts_after}")
    print(f"  → {schemes_path}")
    return summary


def run_v3_auto_pipeline(
    allocation_task_id: int,
    *,
    top_k: int = DEFAULT_TOP_K,
    plan_count: int = DEFAULT_PLAN_COUNT,
    scheme_count: int | None = None,
    solver_time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    solver_workers: int | None = None,
    max_auto_stage: str | None = None,
    skip_diversity: bool = False,
    requested_generation_mode: str | None = None,
    output_dir: Path | str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run V3 automatically: first feasible → quality → optional diversity."""
    started = time.perf_counter()
    auto_dir = _resolve_output_dir(allocation_task_id, output_dir)
    auto_dir.mkdir(parents=True, exist_ok=True)
    requested_scheme_count = max(1, scheme_count or 3)
    resolved_max_auto_stage = _resolve_max_auto_stage(
        max_auto_stage,
        requested_generation_mode=requested_generation_mode,
        skip_diversity=skip_diversity,
    )
    stages: list[dict[str, Any]] = []
    best_result: dict[str, Any] | None = None
    best_stage = ""

    def emit(stage: str, message: str, progress: int, **extra: Any) -> None:
        if progress_callback is not None:
            progress_callback({"stage": stage, "message": message, "progress": progress, **extra})

    def run_stage(
        stage: str,
        *,
        mode: str,
        stage_scheme_count: int,
        stage_solver_time_limit: float,
        stage_solver_workers: int,
        stage_progress_base: int,
        stage_output_name: str,
    ) -> dict[str, Any] | None:
        stage_strategy = _stage_strategy(
            stage,
            workers=stage_solver_workers,
            time_limit=stage_solver_time_limit,
            top_k=top_k,
            raw_plan_count=plan_count,
            cp_plan_count=None,
            scheme_count=stage_scheme_count,
            objective_mode=mode,
        )
        stage_started = time.perf_counter()
        stage_record: dict[str, Any] = {
            "stage": stage,
            "mode": mode,
            "status": "RUNNING",
            "scheme_count_requested": stage_scheme_count,
            "solver_time_limit_seconds": stage_solver_time_limit,
            "solver_workers": stage_solver_workers,
            "stage_strategy": stage_strategy,
        }
        stages.append(stage_record)
        emit(
            stage,
            _auto_stage_message(stage, "start"),
            stage_progress_base,
            generation_mode=mode,
            scheme_count=stage_scheme_count,
            stage_strategy=stage_strategy,
            strategy=_format_stage_strategy(stage_strategy),
        )
        try:
            result = run_v3_pipeline(
                allocation_task_id,
                top_k=top_k,
                plan_count=plan_count,
                scheme_count=stage_scheme_count,
                solver_time_limit_seconds=stage_solver_time_limit,
                solver_workers=stage_solver_workers,
                generation_mode=mode,
                output_dir=auto_dir / stage_output_name,
                progress_callback=progress_callback,
            )
            stage_record.update({
                "status": "SUCCESS",
                "output_dir": result.get("output_dir"),
                "summary_path": result.get("summary_path"),
                "schemes_path": result.get("schemes_path"),
                "preflight_report_path": result.get("preflight_report_path"),
                "cp_sat_summary_path": result.get("cp_sat_summary_path"),
                "scheme_count": result.get("scheme_count"),
                "solver_status": result.get("solver_status"),
                "runtime_s": round(time.perf_counter() - stage_started, 2),
            })
            emit(
                stage,
                _auto_stage_message(stage, "success"),
                min(stage_progress_base + 12, 95),
                output_dir=result.get("output_dir"),
                scheme_count=result.get("scheme_count"),
                stage_strategy=result.get("stage_strategy") or stage_strategy,
                strategy=_format_stage_strategy(result.get("stage_strategy") or stage_strategy),
            )
            return result
        except Exception as exc:
            stage_record.update({
                "status": "FAILED",
                "error": f"{type(exc).__name__}: {exc}",
                "runtime_s": round(time.perf_counter() - stage_started, 2),
            })
            emit(
                stage,
                _auto_stage_message(stage, "failed"),
                min(stage_progress_base + 12, 95),
                error=stage_record["error"],
                stage_strategy=stage_strategy,
                strategy=_format_stage_strategy(stage_strategy),
            )
            return None

    emit(
        "PREFLIGHT",
        f"AUTO 流水线启动：阶段上限 {resolved_max_auto_stage}。",
        3,
        max_auto_stage=resolved_max_auto_stage,
        skip_diversity=skip_diversity,
    )
    first_result = run_stage(
        "FIRST_FEASIBLE",
        mode="FEASIBILITY",
        stage_scheme_count=1,
        stage_solver_time_limit=_auto_first_feasible_time_limit(solver_time_limit_seconds),
        stage_solver_workers=_resolve_solver_workers(solver_workers, "FIRST_FEASIBLE"),
        stage_progress_base=8,
        stage_output_name="first_feasible",
    )
    if first_result is not None:
        best_result = first_result
        best_stage = "FIRST_FEASIBLE"

    quality_result: dict[str, Any] | None = None
    if _auto_stage_enabled("QUALITY_OPTIMIZATION", resolved_max_auto_stage) and best_result is not None:
        quality_result = run_stage(
            "QUALITY_OPTIMIZATION",
            mode="QUALITY",
            stage_scheme_count=1,
            stage_solver_time_limit=solver_time_limit_seconds,
            stage_solver_workers=_resolve_solver_workers(solver_workers, "QUALITY_OPTIMIZATION"),
            stage_progress_base=38,
            stage_output_name="quality",
        )
        if quality_result is not None:
            best_result = quality_result
            best_stage = "QUALITY_OPTIMIZATION"
    elif not _auto_stage_enabled("QUALITY_OPTIMIZATION", resolved_max_auto_stage):
        stages.append({"stage": "QUALITY_OPTIMIZATION", "status": "SKIPPED", "reason": "MAX_AUTO_STAGE"})
        emit("QUALITY_OPTIMIZATION", "AUTO 阶段上限为首个可行解，跳过质量优化。", 38)
    else:
        stages.append({"stage": "QUALITY_OPTIMIZATION", "status": "SKIPPED", "reason": "FIRST_FEASIBLE_FAILED"})
        emit("QUALITY_OPTIMIZATION", "首个可行解失败，跳过质量优化。", 38)

    diversity_result: dict[str, Any] | None = None
    if _auto_stage_enabled("DIVERSITY_SEARCH", resolved_max_auto_stage) and quality_result is not None:
        diversity_result = run_stage(
            "DIVERSITY_SEARCH",
            mode="QUALITY",
            stage_scheme_count=max(2, requested_scheme_count),
            stage_solver_time_limit=solver_time_limit_seconds,
            stage_solver_workers=_resolve_solver_workers(solver_workers, "DIVERSITY_SEARCH"),
            stage_progress_base=68,
            stage_output_name="diversity",
        )
        if diversity_result is not None:
            best_result = diversity_result
            best_stage = "DIVERSITY_SEARCH"
    elif not _auto_stage_enabled("DIVERSITY_SEARCH", resolved_max_auto_stage):
        stages.append({"stage": "DIVERSITY_SEARCH", "status": "SKIPPED", "reason": "MAX_AUTO_STAGE"})
        emit("DIVERSITY_SEARCH", "大规模/AUTO 阶段配置要求跳过多方案搜索。", 68)
    else:
        stages.append({"stage": "DIVERSITY_SEARCH", "status": "SKIPPED", "reason": "QUALITY_OPTIMIZATION_FAILED"})
        emit("DIVERSITY_SEARCH", "质量优化未成功，保留已有最佳方案并跳过多方案搜索。", 68)

    runtime_s = round(time.perf_counter() - started, 2)
    summary = {
        "architecture": "v3_auto_pipeline",
        "allocation_task_id": allocation_task_id,
        "generation_mode": "AUTO",
        "max_auto_stage": resolved_max_auto_stage,
        "skip_diversity": not _auto_stage_enabled("DIVERSITY_SEARCH", resolved_max_auto_stage),
        "output_dir": best_result.get("output_dir") if best_result else str(auto_dir),
        "best_stage": best_stage or None,
        "best_result": best_result,
        "stages": stages,
        "runtime_s": runtime_s,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    summary_path = auto_dir / "auto_summary.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if best_result is None:
        emit("FAILED", "AUTO 流水线未找到可用方案，请查看 auto_summary.json 和 preflight_report.json。", 100, summary_path=str(summary_path))
        raise ValueError(f"V3 AUTO pipeline failed: summary={summary_path}")

    emit(
        "PERSISTING",
        "AUTO 流水线已选出最佳可用结果，准备交给后端入库...",
        96,
        output_dir=summary["output_dir"],
        best_stage=best_stage,
        summary_path=str(summary_path),
    )
    emit(
        "DONE",
        "AUTO 排课流水线完成。",
        100,
        output_dir=summary["output_dir"],
        best_stage=best_stage,
        summary_path=str(summary_path),
        runtime_s=runtime_s,
    )
    return summary


# ── internal helpers ──────────────────────────────────────────────────

def _resolve_solver_workers(value: int | None, stage: str) -> int:
    if value is not None:
        return max(1, int(value))
    return DEFAULT_STAGE_SOLVER_WORKERS.get(stage, 8)


def _stage_strategy(
    stage: str,
    *,
    workers: int,
    time_limit: float,
    top_k: int,
    raw_plan_count: int,
    cp_plan_count: int | None,
    scheme_count: int,
    objective_mode: str,
) -> dict[str, Any]:
    descriptions = {
        "FIRST_FEASIBLE": "快速寻找首个无冲突可行解",
        "QUALITY_OPTIMIZATION": "在可行基础上优化模型分和教师画像目标",
        "DIVERSITY_SEARCH": "搜索多方案并进一步优化候选覆盖",
    }
    return {
        "stage": stage,
        "workers": workers,
        "time_limit_seconds": time_limit,
        "top_k": top_k,
        "raw_plan_count": raw_plan_count,
        "cp_plan_count": cp_plan_count,
        "scheme_count": scheme_count,
        "objective_mode": objective_mode,
        "description": descriptions.get(stage, "执行 V3 CP-SAT 排课阶段"),
    }


def _format_stage_strategy(strategy: dict[str, Any]) -> str:
    return (
        f"workers={strategy.get('workers')}, "
        f"time_limit={strategy.get('time_limit_seconds')}s, "
        f"top_k={strategy.get('top_k')}, "
        f"raw_plan_count={strategy.get('raw_plan_count')}, "
        f"cp_plan_count={strategy.get('cp_plan_count')}, "
        f"scheme_count={strategy.get('scheme_count')}, "
        f"objective_mode={strategy.get('objective_mode')}; "
        f"{strategy.get('description')}"
    )


def _resolve_output_dir(allocation_task_id: int, output_dir: Path | str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
    return OUTPUT_ROOT / f"task_{allocation_task_id}_{ts}"


def _run_placement_inference(
    *,
    teaching_tasks: list[dict],
    task_cg_map: dict[int, str],
    courses: dict[str, dict],
    classrooms: dict[str, dict],
    class_groups: dict[str, dict],
    teachers: dict[str, dict],
    model: DirectPlacementModel,
    top_k: int,
    output_path: Path,
    allocation_task_id: int,
    raw_config: dict[str, Any] | None,
) -> int:
    """Run model inference on all tasks in parallel, write placement candidates JSONL."""
    workers = min(8, max(1, (os.cpu_count() or 4) - 1))

    def _infer_one(task: dict) -> str | None:
        row = _build_candidate_row(
            task=task,
            task_cg_map=task_cg_map,
            courses=courses,
            classrooms=classrooms,
            class_groups=class_groups,
            teachers=teachers,
            model=model,
            top_k=top_k,
            allocation_task_id=allocation_task_id,
            raw_config=raw_config,
        )
        if row is None:
            return None
        return json.dumps(row, ensure_ascii=False, default=str)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_infer_one, t): t for t in teaching_tasks}
            for future in as_completed(futures):
                line = future.result()
                if line is not None:
                    f.write(line + "\n")
                    count += 1
    return count


def _run_template_generation_parallel(
    *,
    candidates_path: str,
    output_path: Path,
    plan_count: int,
) -> int:
    """Generate task plans in parallel using multiple threads.

    Each thread has its own WeekUsageAllocator to avoid contention.
    """
    workers = min(8, max(1, (os.cpu_count() or 4) - 1))
    candidate_rows = _read_candidate_rows(Path(candidates_path))
    teacher_profiles = _load_teacher_profiles()
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def _gen_one(candidate_row: dict) -> str | None:
        allocator = WeekUsageAllocator()
        try:
            row = _build_task_plan_row(
                candidate_row,
                plan_count=plan_count,
                generated_at=generated_at,
                allocator=allocator,
                teacher_profiles=teacher_profiles,
            )
        except Exception:
            return None
        return json.dumps(row, ensure_ascii=False, default=str)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_gen_one, row): idx
                for idx, (_, row) in enumerate(candidate_rows)
            }
            for future in as_completed(futures):
                line = future.result()
                if line is not None:
                    f.write(line + "\n")
                    count += 1
    return count


def _build_candidate_row(
    *,
    task: dict,
    task_cg_map: dict[int, str],
    courses: dict[str, dict],
    classrooms: dict[str, dict],
    class_groups: dict[str, dict],
    teachers: dict[str, dict],
    model: DirectPlacementModel,
    top_k: int,
    allocation_task_id: int,
    raw_config: dict[str, Any] | None,
) -> dict | None:
    """Build one placement candidate row for a teaching task."""
    tid = task.get("id")
    course_code = (task.get("course_code") or "").strip()
    teacher_name = (task.get("teacher_name") or "").strip()
    class_name = (task_cg_map.get(tid) or task.get("class_group") or "").strip()

    course = courses.get(course_code, {})
    cg = class_groups.get(class_name, {})
    teacher = teachers.get(teacher_name, {})

    if not course_code or not class_name:
        return None
    allowed_day_periods = _allowed_day_periods(raw_config)

    # Build feature dict for the model
    row_dict = {
        "course_name": course.get("name", ""),
        "course_code": course_code,
        "teacher_no": teacher.get("no", teacher.get("teacher_no", "")),
        "teacher_name": teacher_name,
        "class_name": class_name,
        "class_major": cg.get("major", ""),
        "class_department": cg.get("department", ""),
        "class_grade": str(cg.get("grade", "")),
        "student_count": str(task.get("student_count") or cg.get("student_count") or 0),
        "total_hours": str(task.get("total_hours") or course.get("hours") or 0),
        "course_type": course.get("course_type", ""),
        "required_room_type": course.get("required_room_type", ""),
    }

    try:
        predictions = model.predict_topk(row_dict, top_k=top_k)
    except Exception:
        return None

    resources = []
    seen_resource_keys: set[str] = set()
    for resource_key, score in predictions:
        parsed = _parse_resource_key(resource_key)
        if parsed is None:
            continue
        classroom_name, day_of_week, period_index = parsed
        if (day_of_week, period_index) not in allowed_day_periods:
            continue
        room = classrooms.get(classroom_name, {})
        if resource_key in seen_resource_keys:
            continue
        seen_resource_keys.add(resource_key)
        resources.append({
            "resource_key": resource_key,
            "slot": {
                "day_of_week": day_of_week,
                "period_index": period_index,
            },
            "classroom": {
                "id": room.get("id"),
                "name": classroom_name,
                "classroom_type": room.get("classroom_type", ""),
            },
            "score": round(score, 6),
        })

    _append_day_period_fallback_resources(
        resources=resources,
        seen_resource_keys=seen_resource_keys,
        allowed_day_periods=allowed_day_periods,
        classrooms=classrooms,
        required_room_type=str(course.get("required_room_type") or ""),
        student_count=int(task.get("student_count") or cg.get("student_count") or 0),
        teaching_task_id=int(tid or 0),
    )
    resources = _prioritize_day_period_coverage(resources, allowed_day_periods)

    if not resources:
        return None

    total_hours = int(float(task.get("total_hours") or course.get("hours") or 0))
    total_sessions = int(task.get("total_sessions") or total_hours // 2)

    return {
        "allocation_task_id": allocation_task_id,
        "teaching_task_id": task.get("id"),
        "input": row_dict,
        "task": {
            "teaching_task_id": task.get("id"),
            "teacher_name": teacher_name,
            "teacher_id": teacher.get("id"),
            "class_group_name": class_name,
            "class_group_ids": [cg.get("id")] if cg.get("id") else [],
            "total_hours": total_hours,
            "total_sessions": total_sessions,
            "course_code": course_code,
            "course_type": course.get("course_type", ""),
            "required_room_type": course.get("required_room_type", ""),
        },
        "resources": resources,
        "meta": {
            "source": "v3_placement_direct",
            "model": "lightgbm_multiclass",
            "top_k": top_k,
            "num_classes": len(model.resource_by_label),
            "allowed_weeks": _allowed_weeks(raw_config),
        },
    }


def _append_day_period_fallback_resources(
    *,
    resources: list[dict[str, Any]],
    seen_resource_keys: set[str],
    allowed_day_periods: set[tuple[int, int]],
    classrooms: dict[str, dict],
    required_room_type: str,
    student_count: int,
    teaching_task_id: int,
) -> None:
    room_pool = _fallback_room_pool(classrooms, required_room_type, student_count)
    if not room_pool:
        return
    counts_by_slot: Counter[tuple[int, int]] = Counter()
    for resource in resources:
        slot = resource.get("slot") or {}
        key = (int(slot.get("day_of_week") or 0), int(slot.get("period_index") or 0))
        if key in allowed_day_periods:
            counts_by_slot[key] += 1

    minimum_alternatives_per_slot = min(3, len(room_pool))
    for day, period in sorted(allowed_day_periods):
        offset = 0
        while counts_by_slot[(day, period)] < minimum_alternatives_per_slot and offset < len(room_pool):
            room = _pick_fallback_room(room_pool, teaching_task_id, day, period, offset=offset)
            offset += 1
            room_name = str(room.get("name") or "")
            if not room_name:
                continue
            resource_key = f"{room_name}|{day}|{period}"
            if resource_key in seen_resource_keys:
                continue
            seen_resource_keys.add(resource_key)
            counts_by_slot[(day, period)] += 1
            resources.append({
                "resource_key": resource_key,
                "slot": {
                    "day_of_week": day,
                    "period_index": period,
                },
                "classroom": {
                    "id": room.get("id"),
                    "name": room_name,
                    "classroom_type": room.get("classroom_type", ""),
                },
                "score": 0.000001,
                "source": "day_period_fallback",
            })


def _prioritize_day_period_coverage(
    resources: list[dict[str, Any]],
    allowed_day_periods: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Spread early plan options across day/periods and room alternatives."""
    by_slot: dict[tuple[int, int], list[dict[str, Any]]] = {key: [] for key in allowed_day_periods}
    for resource in resources:
        slot = resource.get("slot") or {}
        key = (int(slot.get("day_of_week") or 0), int(slot.get("period_index") or 0))
        if key not in allowed_day_periods:
            continue
        by_slot[key].append(resource)

    for slot_resources in by_slot.values():
        slot_resources.sort(
            key=lambda resource: (
                -float(resource.get("score") or 0.0),
                str((resource.get("classroom") or {}).get("name") or ""),
                int((resource.get("classroom") or {}).get("id") or 0),
            )
        )

    ordered: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    max_depth = max((len(slot_resources) for slot_resources in by_slot.values()), default=0)
    for depth in range(max_depth):
        for key in sorted(by_slot):
            slot_resources = by_slot[key]
            if depth >= len(slot_resources):
                continue
            resource = slot_resources[depth]
            if id(resource) in used_ids:
                continue
            ordered.append(resource)
            used_ids.add(id(resource))

    ordered.extend(resource for resource in resources if id(resource) not in used_ids)
    return ordered


def _fallback_room_pool(classrooms: dict[str, dict], required_room_type: str, student_count: int) -> list[dict]:
    required = required_room_type.strip()
    rooms = [
        room
        for room in classrooms.values()
        if int(room.get("capacity") or 0) >= max(0, student_count)
    ]
    if required:
        exact = [room for room in rooms if str(room.get("classroom_type") or "").strip() == required]
        if exact:
            rooms = exact
    return sorted(
        rooms,
        key=lambda room: (
            int(room.get("capacity") or 0),
            int(room.get("id") or 0),
            str(room.get("name") or ""),
        ),
    )


def _pick_fallback_room(room_pool: list[dict], teaching_task_id: int, day: int, period: int, *, offset: int = 0) -> dict:
    index = (teaching_task_id * 31 + day * 7 + period + offset) % len(room_pool)
    return room_pool[index]


def _parse_resource_key(resource_key: str) -> tuple[str, int, int] | None:
    """Parse 'classroom_name|day|period' into components."""
    parts = resource_key.split("|")
    if len(parts) != 3:
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _resolve_scheme_count(raw_config: dict[str, Any] | None) -> int:
    if not raw_config:
        return 1
    try:
        value = int(raw_config.get("scheme_count") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 20))


def _is_auto_generation_mode(mode: str | None) -> bool:
    normalized = str(mode or DEFAULT_GENERATION_MODE).strip().upper()
    return normalized in AUTO_GENERATION_MODES or normalized.startswith("AUTO_")


def _resolve_max_auto_stage(
    explicit_stage: str | None,
    *,
    requested_generation_mode: str | None,
    skip_diversity: bool,
) -> str:
    if explicit_stage:
        return _normalize_auto_stage(explicit_stage)
    mode = str(requested_generation_mode or "").strip().upper()
    if mode in {"AUTO_FEASIBLE", "AUTO_FIRST_FEASIBLE", "AUTO_FIRST"}:
        return "FIRST_FEASIBLE"
    if mode in {"AUTO_FULL", "AUTO_DIVERSITY", "AUTO_ALL"}:
        return "DIVERSITY_SEARCH"
    if skip_diversity or mode in {"AUTO_QUALITY", "AUTO_NO_DIVERSITY", "AUTO_FAST", "AUTO_STRESS"}:
        return "QUALITY_OPTIMIZATION"
    return "QUALITY_OPTIMIZATION"


def _normalize_auto_stage(stage: str) -> str:
    normalized = str(stage or "").strip().upper()
    aliases = {
        "FIRST": "FIRST_FEASIBLE",
        "FEASIBLE": "FIRST_FEASIBLE",
        "FEASIBILITY": "FIRST_FEASIBLE",
        "FIRST_SOLUTION": "FIRST_FEASIBLE",
        "QUALITY": "QUALITY_OPTIMIZATION",
        "QUALITY_OPTIMIZATION": "QUALITY_OPTIMIZATION",
        "DIVERSITY": "DIVERSITY_SEARCH",
        "DIVERSITY_SEARCH": "DIVERSITY_SEARCH",
    }
    if normalized not in aliases:
        raise ValueError(
            "max_auto_stage must be one of FIRST_FEASIBLE, QUALITY_OPTIMIZATION, DIVERSITY_SEARCH"
        )
    return aliases[normalized]


def _auto_stage_enabled(stage: str, max_auto_stage: str) -> bool:
    return AUTO_STAGE_ORDER.index(stage) <= AUTO_STAGE_ORDER.index(max_auto_stage)


def _auto_first_feasible_time_limit(configured_time_limit: float) -> float:
    return max(30.0, min(float(configured_time_limit), 300.0))


def _widen_first_feasible_candidates(
    *,
    task_count: int,
    generation_mode: str,
    placement_top_k: int,
    raw_plan_count: int,
    cp_plan_count: int,
) -> tuple[int, int, int]:
    if generation_mode not in FEASIBILITY_MODES or task_count < LARGE_STRESS_TASK_THRESHOLD:
        return placement_top_k, raw_plan_count, cp_plan_count
    return (
        max(placement_top_k, FIRST_FEASIBLE_MIN_TOP_K),
        max(raw_plan_count, FIRST_FEASIBLE_MIN_PLAN_COUNT),
        max(cp_plan_count, FIRST_FEASIBLE_MIN_CP_PLAN_COUNT),
    )


def _auto_stage_message(stage: str, status: str) -> str:
    messages = {
        ("FIRST_FEASIBLE", "start"): "正在判断是否存在首个无冲突可行解...",
        ("FIRST_FEASIBLE", "success"): "首个可行解已找到。",
        ("FIRST_FEASIBLE", "failed"): "首个可行解未找到，AUTO 流水线停止。",
        ("QUALITY_OPTIMIZATION", "start"): "正在结合教师画像和美观目标优化高质量方案...",
        ("QUALITY_OPTIMIZATION", "success"): "高质量方案已生成。",
        ("QUALITY_OPTIMIZATION", "failed"): "质量优化失败，保留已有可行解。",
        ("DIVERSITY_SEARCH", "start"): "正在基于高质量方案搜索其他候选方案...",
        ("DIVERSITY_SEARCH", "success"): "多方案搜索完成，已选用最佳可用结果。",
        ("DIVERSITY_SEARCH", "failed"): "多方案搜索失败，保留已有高质量结果。",
    }
    return messages.get((stage, status), f"{stage} {status}")


def _resolve_generation_mode(raw_config: dict[str, Any] | None, explicit_mode: str | None) -> str:
    raw_value = explicit_mode
    if raw_value is None and raw_config:
        raw_value = raw_config.get("generation_mode") or raw_config.get("scheduling_mode")
    mode = str(raw_value or DEFAULT_SINGLE_GENERATION_MODE).strip().upper()
    if mode in {"FEASIBLE", "FIRST", "FIRST_SOLUTION"}:
        return "FEASIBILITY"
    if mode in AUTO_GENERATION_MODES:
        return DEFAULT_SINGLE_GENERATION_MODE
    if mode not in {"FEASIBILITY", "QUALITY", "STRESS"}:
        return DEFAULT_SINGLE_GENERATION_MODE
    return mode


def _resolve_plan_count(raw_config: dict[str, Any] | None, default: int) -> int:
    raw_value = None
    if raw_config:
        raw_value = raw_config.get("raw_plan_count") or raw_config.get("plan_count")
    return _bounded_int(raw_value, default, 1, MAX_PLAN_COUNT)


def _resolve_solver_time_limit(raw_config: dict[str, Any] | None, default: float) -> float:
    raw_value = raw_config.get("solver_time_limit_seconds") if raw_config else None
    value = _parse_float(raw_value, default)
    return max(1.0, min(value, MAX_SOLVER_TIME_LIMIT_SECONDS))


def _resolve_bounded_int(
    raw_config: dict[str, Any] | None,
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = raw_config.get(key) if raw_config else None
    return _bounded_int(raw_value, default, minimum, maximum)


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _resolve_cp_sat_objective_weights(raw_config: dict[str, Any] | None) -> dict[str, float]:
    model_weight = _parse_float(raw_config.get("model_weight") if raw_config else None, MODEL_OBJECTIVE_WEIGHT)
    teacher_scale = _parse_float(raw_config.get("teacher_profile_penalty_scale") if raw_config else None, 100.0)
    teacher_multiplier = max(0.0, teacher_scale) / 100.0
    return {
        "model": max(0.0, model_weight),
        "teacher_profile_score": TEACHER_PROFILE_OBJECTIVE_WEIGHT * teacher_multiplier,
        "teacher_profile_penalty": TEACHER_PROFILE_PENALTY_WEIGHT * teacher_multiplier,
    }


def _parse_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _write_preflight_report(
    task_plans_path: Path,
    output_dir: Path,
    *,
    expected_task_count: int,
    placement_top_k: int,
    raw_plan_count: int,
    cp_plan_count: int,
    generation_mode: str,
) -> dict[str, Any]:
    rows = _read_jsonl(task_plans_path)
    plan_counts = [len(row.get("plans") or []) for row in rows]
    no_plan_rows = [row for row in rows if not row.get("plans")]
    no_candidate_task_count = max(0, expected_task_count - len(rows))
    teacher_sessions: Counter[int] = Counter()
    class_sessions: Counter[int] = Counter()
    resource_slots: Counter[str] = Counter()
    room_type_slots: dict[str, set[str]] = defaultdict(set)
    task_room_type_requirements: Counter[str] = Counter()
    risk_items: list[dict[str, Any]] = []

    for row in rows:
        task = row.get("task") or {}
        teacher_id = int(task.get("teacher_id") or 0)
        total_sessions = int(task.get("total_sessions") or 0)
        if teacher_id > 0:
            teacher_sessions[teacher_id] += total_sessions
        for class_group_id in task.get("class_group_ids") or []:
            cid = int(class_group_id or 0)
            if cid > 0:
                class_sessions[cid] += total_sessions
        if not row.get("plans"):
            risk_items.append({
                "type": "NO_PLAN",
                "teaching_task_id": row.get("teaching_task_id"),
                "teacher_id": teacher_id,
                "reason": row.get("error") or "NO_VALID_TASK_PLAN",
            })
        required_room_type = str(task.get("required_room_type") or task.get("course_type") or "").strip() or "UNKNOWN"
        task_room_type_requirements[required_room_type] += 1
        for plan in (row.get("plans") or [])[:10]:
            for segment in plan.get("segments") or []:
                resource = segment.get("resource") or {}
                slot = resource.get("slot") or {}
                classroom = resource.get("classroom") or {}
                key = f"{classroom.get('id') or classroom.get('name')}|{slot.get('day_of_week')}|{slot.get('period_index')}"
                resource_slots[key] += 1
                room_type = str(classroom.get("classroom_type") or "UNKNOWN").strip() or "UNKNOWN"
                room_type_slots[room_type].add(key)

    if plan_counts:
        sorted_counts = sorted(plan_counts)
        p50 = sorted_counts[len(sorted_counts) // 2]
        min_plans = sorted_counts[0]
        max_plans = sorted_counts[-1]
        avg_plans = round(sum(plan_counts) / len(plan_counts), 2)
    else:
        p50 = min_plans = max_plans = avg_plans = 0

    teacher_capacity_risk = [
        {"teacher_id": tid, "sessions": count}
        for tid, count in teacher_sessions.most_common(20)
        if count > 90
    ]
    class_capacity_risk = [
        {"class_group_id": cid, "sessions": count}
        for cid, count in class_sessions.most_common(20)
        if count > 120
    ]
    hot_resource_slots = [
        {"resource_slot": key, "candidate_plan_hits": count}
        for key, count in resource_slots.most_common(20)
        if count > max(50, len(rows) * 0.02)
    ]
    room_type_capacity_risk = [
        {
            "room_type": room_type,
            "task_count": task_count,
            "candidate_slot_count": len(room_type_slots.get(room_type, set())),
        }
        for room_type, task_count in task_room_type_requirements.most_common()
        if len(room_type_slots.get(room_type, set())) == 0
    ][:20]
    risks: list[dict[str, Any]] = []
    if no_candidate_task_count > 0:
        risks.append({"type": "NO_CANDIDATE_TASKS", "count": no_candidate_task_count})
    if no_plan_rows:
        risks.append({"type": "NO_PLAN_TASKS", "count": len(no_plan_rows)})
    if teacher_capacity_risk:
        risks.append({"type": "TEACHER_LOAD_HIGH", "count": len(teacher_capacity_risk)})
    if class_capacity_risk:
        risks.append({"type": "CLASS_LOAD_HIGH", "count": len(class_capacity_risk)})
    if room_type_capacity_risk:
        risks.append({"type": "ROOM_TYPE_CAPACITY_LOW", "count": len(room_type_capacity_risk)})
    estimated_feasible = not no_plan_rows and no_candidate_task_count == 0
    report_path = output_dir / "preflight_report.json"
    summary = {
        "summary_path": str(report_path),
        "report_path": str(report_path),
        "task_count": len(rows),
        "expected_task_count": expected_task_count,
        "no_candidate_task_count": no_candidate_task_count,
        "no_plan_task_count": len(no_plan_rows),
        "empty_plan_task_count": len(no_plan_rows),
        "plan_count_min": min_plans,
        "plan_count_p50": p50,
        "plan_count_avg": avg_plans,
        "plan_count_max": max_plans,
        "plan_count_per_task": {
            "min": min_plans,
            "p50": p50,
            "avg": avg_plans,
            "max": max_plans,
        },
        "teacher_capacity_risk": teacher_capacity_risk,
        "class_capacity_risk": class_capacity_risk,
        "room_type_capacity_risk": room_type_capacity_risk,
        "hot_resource_slots": hot_resource_slots,
        "risk_items": risk_items[:100],
        "risks": risks,
        "estimated_feasible": estimated_feasible,
        "placement_top_k": placement_top_k,
        "raw_plan_count": raw_plan_count,
        "cp_plan_count": cp_plan_count,
        "generation_mode": generation_mode,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _write_cp_task_plans(source_path: Path, target_path: Path, cp_plan_count: int) -> int:
    written = 0
    with source_path.open("r", encoding="utf-8") as source, target_path.open("w", encoding="utf-8") as target:
        for line in source:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            plans = list(row.get("plans") or [])
            if len(plans) > cp_plan_count:
                row["plans"] = _select_cp_plans(plans, cp_plan_count)
                meta = row.setdefault("meta", {})
                meta["raw_plan_count"] = len(plans)
                meta["cp_plan_count"] = len(row["plans"])
                meta["cp_plan_strategy"] = "score_plus_slot_diversity"
            target.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            written += 1
    return written


def _select_cp_plans(plans: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(plans, key=_plan_rank_key)
    selected: list[dict[str, Any]] = []
    used_slot_signatures: set[tuple[tuple[int, int], ...]] = set()
    for plan in ranked:
        signature = _plan_slot_signature(plan)
        if signature in used_slot_signatures and len(selected) < max(1, limit // 2):
            continue
        selected.append(plan)
        used_slot_signatures.add(signature)
        if len(selected) >= limit:
            return selected
    for plan in ranked:
        if plan not in selected:
            selected.append(plan)
        if len(selected) >= limit:
            break
    return selected


def _plan_rank_key(plan: dict[str, Any]) -> tuple[float, int, str]:
    score = float(plan.get("score") or 0.0)
    profile_score = float(plan.get("teacher_profile_score") or 1.0)
    segment_count = len(plan.get("segments") or [])
    return (-(score + 0.15 * profile_score), segment_count, str(plan.get("plan_id") or ""))


def _plan_slot_signature(plan: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    slots = []
    for segment in plan.get("segments") or []:
        slot = ((segment.get("resource") or {}).get("slot") or {})
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        if day > 0 and period > 0:
            slots.append((day, period))
    return tuple(sorted(set(slots)))


def _filter_time_slots(time_slots: list[dict[str, Any]], raw_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    allowed_weeks = _parse_int_set(raw_config.get("allowed_weeks") if raw_config else None) or DEFAULT_ALLOWED_WEEKS
    allowed_weekdays = (
        _parse_int_set(raw_config.get("allowed_weekdays") if raw_config else None)
        or DEFAULT_ALLOWED_WEEKDAYS
    )
    allowed_periods = (
        _parse_int_set(raw_config.get("allowed_periods") if raw_config else None)
        or DEFAULT_ALLOWED_PERIODS
    )
    result = []
    for slot in time_slots:
        week = int(slot.get("week_number") or 0)
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        if week not in allowed_weeks:
            continue
        if day not in allowed_weekdays:
            continue
        if period not in allowed_periods:
            continue
        result.append(slot)
    return result


def _time_slot_id_by_coord(time_slots: list[dict[str, Any]]) -> dict[tuple[int, int, int], int]:
    return {
        (int(slot["week_number"]), int(slot["day_of_week"]), int(slot["period_index"])): int(slot["id"])
        for slot in time_slots
    }


def _allowed_day_periods(raw_config: dict[str, Any] | None) -> set[tuple[int, int]]:
    allowed_days = (
        _parse_int_set(raw_config.get("allowed_weekdays") if raw_config else None)
        or DEFAULT_ALLOWED_WEEKDAYS
    )
    allowed_periods = (
        _parse_int_set(raw_config.get("allowed_periods") if raw_config else None)
        or DEFAULT_ALLOWED_PERIODS
    )
    days = sorted(allowed_days)
    periods = sorted(allowed_periods)
    return {(day, period) for day in days for period in periods}


def _allowed_weeks(raw_config: dict[str, Any] | None) -> list[int]:
    allowed = _parse_int_set(raw_config.get("allowed_weeks") if raw_config else None) or DEFAULT_ALLOWED_WEEKS
    return sorted(allowed)


def _parse_int_set(value: Any) -> set[int] | None:
    if value is None:
        return None
    raw = str(value).strip().strip("[]").replace(" ", "")
    if not raw:
        return None
    result: set[int] = set()
    for part in raw.split(","):
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            pass
    return result or None


def _audit_schemes_jsonl(path: Path) -> dict[str, int]:
    total = {"teacher": 0, "class": 0, "room": 0, "time_slot_mapping": 0, "hour_mismatch": 0}
    for scheme in _read_jsonl(path):
        conflicts = audit_scheme_items(list(scheme.get("items") or []))
        for key, value in conflicts.items():
            total[key] = total.get(key, 0) + int(value)
    return total
