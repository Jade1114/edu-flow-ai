"""GA pipeline orchestration — scheme generation, evolution, and task-driven pipeline."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Optional

import pandas as pd

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

from ml import ml_logger
from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    fetch_classrooms,
    fetch_tasks,
    fetch_teacher_profiles,
    fetch_time_slots,
)
from ml.scheduling.infra.constants import (
    CANDIDATE_DIAGNOSTICS,
    DEFAULT_CANDIDATE_POOL_SIZE,
    DEFAULT_CANDIDATE_TOP_N,
    DEFAULT_ELITE_SIZE,
    DEFAULT_GENERATIONS,
    DEFAULT_MUTATION_RATE,
    DEFAULT_POPULATION_SIZE,
    DEFAULT_PREDICTED_SCORE_WEIGHT,
    DEFAULT_RULE_SCORE_WEIGHT,
    DEFAULT_HARD_CONFLICT_PENALTY,
    DEFAULT_TOURNAMENT_SIZE,
    MODEL_PATH,
    FEATURE_SCHEMA_PATH,
    PROJECT_LOG_DIR,
    TEACHER_PENALTIES_FILENAME,
)
from ml.scheduling.domain.features import effective_required_room_type, periods_needed
from ml.scheduling.infra.filters import filter_tasks, filter_time_slots, parse_teaching_task_ids
from ml.scheduling.ga.fitness import (
    evaluate_individual,
    individual_assignments,
    individual_rows,
    random_individual,
    repair_individual,
    summarize_individual_conflict_hotspots,
)
from ml.scheduling.ga.ga_operators import crossover, mutate, tournament_select
from ml.scheduling.infra.generation_config import config_float, load_generation_config, rule_weights_from_config
from ml.scheduling.infra.lightgbm import load_optional_lightgbm
from ml.scheduling.ga.candidates import build_candidate_pools
from ml.scheduling.infra.output import (
    print_summary,
    summarize_metrics,
    summarize_scheme,
    write_candidate_diagnostics,
    write_schemes_json,
)
from ml.scheduling.infra.runtime import RUN_TIMINGS, add_timing, configure_python_log, log_chain
from ml.scheduling.domain.teacher_penalties import (
    build_teacher_penalties_from_profiles,
    load_teacher_penalties,
    summarize_teacher_penalties,
    write_teacher_penalties,
)


def parse_int_set(raw_value: Any) -> set[int] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (list, tuple, set)):
        values = list(raw_value)
    else:
        values = [raw_value]
    parsed = {int(v) for v in values if str(v).strip()}
    return parsed or None


def evolve_population(
    pools: list[dict[str, Any]],
    rng: random.Random,
    *,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    fitness_kwargs: dict[str, float],
) -> list[dict[str, Any]]:
    init_started_at = perf_counter()
    population = [random_individual(pools, rng) for _ in range(population_size)]
    add_timing("ga_init_time", init_started_at)
    evolution_started_at = perf_counter()
    scored: list[dict[str, Any]] = []
    for generation in range(1, generations + 1):
        scored = [
            {"individual": ind, "metrics": evaluate_individual(ind, pools, **fitness_kwargs)}
            for ind in population
        ]
        scored.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
        if generation == 1 or generation == generations or generation % 10 == 0:
            m = scored[0]["metrics"]
            log_chain("GA 迭代进度", {
                "generation": generation,
                "best_fitness": m["fitness"],
                "best_hard_conflicts": m.get("hard_conflict_count"),
                "candidate_hard_conflicts": m.get("candidate_hard_conflict_count"),
                "teacher_slot_conflicts": m.get("teacher_slot_conflict_count"),
                "room_slot_conflicts": m.get("room_slot_conflict_count"),
                "class_slot_conflicts": m.get("class_slot_conflict_count"),
            })
            ml_logger.ga_iteration(
                generation=generation,
                best_fitness=m["fitness"],
                hard_conflicts=m.get("hard_conflict_count", 0),
                candidate_hard_conflicts=m.get("candidate_hard_conflict_count", 0),
                teacher_slot_conflicts=m.get("teacher_slot_conflict_count", 0),
                room_slot_conflicts=m.get("room_slot_conflict_count", 0),
                class_slot_conflicts=m.get("class_slot_conflict_count", 0),
            )
        next_population = [item["individual"][:] for item in scored[: max(1, min(elite_size, len(scored)))]]
        while len(next_population) < population_size:
            parent_a = tournament_select(scored, tournament_size, rng)
            parent_b = tournament_select(scored, tournament_size, rng)
            child = crossover(parent_a, parent_b, pools, rng)
            mutate(child, pools, mutation_rate, rng)
            repair_started_at = perf_counter()
            next_population.append(repair_individual(child, pools, rng))
            add_timing("repair_time", repair_started_at)
        population = next_population
    add_timing("ga_evolution_time", evolution_started_at)
    scored = [
        {"individual": ind, "metrics": evaluate_individual(ind, pools, **fitness_kwargs)}
        for ind in population
    ]
    scored.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
    return scored


def generate_scheme(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    max_tasks: int | None,
    rng: random.Random,
    candidate_pool_size: int,
    candidate_top_n: int,
    rule_weights: dict[str, float],
    exclude_weekends: bool = False,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
    elite_size: int = DEFAULT_ELITE_SIZE,
    tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    fitness_kwargs: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list, dict[str, Any]]:
    pools = build_candidate_pools(
        tasks=tasks, classrooms=classrooms, time_slots=time_slots,
        teacher_profiles=teacher_profiles, booster=booster, schema=schema,
        max_tasks=max_tasks, rng=rng,
        candidate_pool_size=candidate_pool_size, candidate_top_n=candidate_top_n,
        rule_weights=rule_weights, exclude_weekends=exclude_weekends,
    )
    if not pools:
        raise ValueError("GA candidate pools are empty")
    effective_fitness_kwargs = fitness_kwargs or {}
    scored = evolve_population(
        pools, rng,
        population_size=population_size, generations=generations,
        elite_size=elite_size, tournament_size=tournament_size,
        mutation_rate=mutation_rate, fitness_kwargs=effective_fitness_kwargs,
    )
    best = scored[0]
    repair_started_at = perf_counter()
    best["individual"] = repair_individual(best["individual"], pools, rng, log_unresolved=True)
    add_timing("repair_time", repair_started_at)
    validate_started_at = perf_counter()
    best["metrics"] = evaluate_individual(best["individual"], pools, **effective_fitness_kwargs)
    add_timing("validate_time", validate_started_at)
    rows = individual_rows(best["individual"], pools)
    assignments = individual_assignments(best["individual"], pools)
    metrics = {**best["metrics"], "candidate_pool_count": len(pools)}
    log_chain("GA 最优方案", metrics)
    ml_logger.ga_summary(metrics)
    hotspots = summarize_individual_conflict_hotspots(best["individual"], pools)
    log_chain("GA 最优方案冲突热点", hotspots)
    ml_logger.ga_conflict_hotspots(hotspots)
    return rows, assignments, metrics


def run_ga_pipeline(args: SimpleNamespace) -> dict[str, Any]:
    """Run the full GA scheme generation pipeline for DB-driven task orchestration."""
    configure_python_log(args.log_file)
    generation_config = load_generation_config(args.generation_config)
    allowed_weeks = parse_int_set(generation_config.get("allowedWeeks"))
    allowed_weekdays = parse_int_set(generation_config.get("allowedWeekdays"))
    allowed_periods = parse_int_set(generation_config.get("allowedPeriods"))
    if generation_config:
        log_chain("Generation Config 解析完成", {"config": generation_config})
        ml_logger.generation_config_parsed(generation_config)
    else:
        log_chain("Generation Config 为空，使用默认配置")
    booster, schema, scoring_mode = load_optional_lightgbm(args.model, args.schema)
    log_chain("排课方案生成链路启动", {
        "scoring_mode": scoring_mode, "model_path": str(args.model),
        "schema_path": str(args.schema), "variant_count": args.variant_count,
    })
    ml_logger.pipeline_start(None, {
        "scoring_mode": scoring_mode, "model_path": str(args.model),
        "variant_count": args.variant_count, "population_size": args.population_size,
        "generations": args.generations, "exclude_weekends": args.exclude_weekends,
        "generation_config": generation_config or None,
    })

    load_started_at = perf_counter()
    db_config = load_db_config()
    with connect(db_config) as connection:
        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)
    add_timing("load_data_time", load_started_at)

    tasks = filter_tasks(tasks, parse_teaching_task_ids(args.teaching_task_ids))
    before_config_time_slot_count = len(time_slots)
    time_slots = filter_time_slots(time_slots, args.start_week, args.end_week,
                                   allowed_weeks, allowed_weekdays, allowed_periods)
    if allowed_weeks or allowed_weekdays or allowed_periods:
        log_chain("生成配置时间片硬约束生效", {
            "before_time_slot_count": before_config_time_slot_count,
            "after_time_slot_count": len(time_slots),
            "removed_time_slot_count": before_config_time_slot_count - len(time_slots),
        })
    if args.exclude_weekends:
        before_count = len(time_slots)
        time_slots = [s for s in time_slots if int(s["day_of_week"]) < 6]
        log_chain("周末硬约束生效", {
            "before_time_slot_count": before_count,
            "after_time_slot_count": len(time_slots),
        })
    if not tasks:
        raise ValueError("No teaching tasks available for scheme generation.")
    if not time_slots:
        raise ValueError("No time slots available for scheme generation.")

    before_week_dist = Counter(int(s["week_number"]) for s in time_slots)
    log_chain("时间片周分布（GA 输入）", {
        "total": len(time_slots), "by_week": dict(sorted(before_week_dist.items())),
    })
    log_chain("排课基础数据加载完成", {
        "teaching_task_count": len(tasks), "classroom_count": len(classrooms),
        "time_slot_count": len(time_slots), "teacher_profile_count": len(teacher_profiles),
    })

    teacher_penalties = load_teacher_penalties(args.teacher_penalties)
    penalty_summary = summarize_teacher_penalties(teacher_penalties)
    log_chain("教师画像惩罚由编排层提供", penalty_summary)
    ml_logger.teacher_profile_summary(len(teacher_penalties), penalty_summary)

    rule_weights = rule_weights_from_config(generation_config)
    fitness_kwargs = {
        "predicted_score_weight": args.predicted_score_weight,
        "rule_score_weight": args.rule_score_weight,
        "hard_conflict_penalty": args.hard_conflict_penalty,
        "distribution_penalty_scale": config_float(generation_config, "distributionPenaltyScale", args.distribution_penalty_scale),
        "classroom_stickiness_weight": config_float(generation_config, "classroomStickinessWeight", args.classroom_stickiness_weight),
        "compact_bonus_weight": config_float(generation_config, "compactBonusWeight", args.compact_bonus_weight),
    }
    log_chain("任务配置权重与 GA 适应度参数生效", {
        "rule_weights": rule_weights, "fitness_weights": fitness_kwargs,
    })

    if args.variant_count <= 1:
        rows, _, metrics = generate_scheme(
            tasks=tasks, classrooms=classrooms, time_slots=time_slots,
            teacher_profiles=teacher_penalties, booster=booster, schema=schema,
            max_tasks=args.max_tasks, rng=random.Random(args.random_seed),
            candidate_pool_size=args.candidate_pool_size, candidate_top_n=args.candidate_top_n,
            rule_weights=rule_weights, exclude_weekends=args.exclude_weekends,
            population_size=args.population_size, generations=args.generations,
            elite_size=args.elite_size, tournament_size=args.tournament_size,
            mutation_rate=args.mutation_rate, fitness_kwargs=fitness_kwargs,
        )
        week_dist = Counter(int(r.get("week_number", 0)) for r in rows)
        log_chain("方案周分布", dict(sorted(week_dist.items())))
        write_schemes_json(args.output_dir, [{"items": rows}])
        write_teacher_penalties(teacher_penalties, args.output_dir / TEACHER_PENALTIES_FILENAME)
        ga_summary_path = args.output_dir / "ga_summary.json"
        ga_summary_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        write_candidate_diagnostics(args.output_dir / "candidate_diagnostics.json", CANDIDATE_DIAGNOSTICS, RUN_TIMINGS)
        log_chain("单方案生成完成", {
            "output_path": str(args.output_dir), **summarize_scheme(rows, tasks, args.max_tasks),
            **summarize_metrics(metrics), "timings_ms": dict(RUN_TIMINGS),
        })
        print_summary(rows, tasks, args.max_tasks, ml_logger.service)
        ml_logger.pipeline_complete(None, {
            "scheme_count": 1, "total_fragments": len(rows),
            "output_dir": str(args.output.parent), "timings_ms": dict(RUN_TIMINGS),
        })
        return {
            "output_dir": str(args.output.parent), "scheme_count": 1,
            "schemes": [{"scheme_no": 1, "output_path": str(args.output),
                         **summarize_scheme(rows, tasks, args.max_tasks),
                         **summarize_metrics(metrics)}],
            "item_rows": [rows],
            "ga_summary_path": str(ga_summary_path),
            "candidate_diagnostics_path": str(args.output.parent / "candidate_diagnostics.json"),
            "timings_ms": dict(RUN_TIMINGS),
        }

    summary_rows: list[dict[str, Any]] = []
    all_item_rows: list[list[dict[str, Any]]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_teacher_penalties(teacher_penalties, args.output_dir / TEACHER_PENALTIES_FILENAME)
    for scheme_no in range(1, args.variant_count + 1):
        rng = random.Random(args.random_seed + scheme_no)
        rows, _, metrics = generate_scheme(
            tasks=tasks, classrooms=classrooms, time_slots=time_slots,
            teacher_profiles=teacher_penalties, booster=booster, schema=schema,
            max_tasks=args.max_tasks, rng=rng,
            candidate_pool_size=args.candidate_pool_size, candidate_top_n=args.candidate_top_n,
            rule_weights=rule_weights, exclude_weekends=args.exclude_weekends,
            population_size=args.population_size, generations=args.generations,
            elite_size=args.elite_size, tournament_size=args.tournament_size,
            mutation_rate=args.mutation_rate, fitness_kwargs=fitness_kwargs,
        )
        summary = summarize_scheme(rows, tasks, args.max_tasks)
        summary_rows.append({"scheme_no": scheme_no, **summary, **summarize_metrics(metrics)})
        all_item_rows.append(rows)
        week_dist = Counter(int(r.get("week_number", 0)) for r in rows)
        log_chain(f"方案 {scheme_no} 周分布", dict(sorted(week_dist.items())))

    write_schemes_json(args.output_dir, [{"items": r} for r in all_item_rows])
    ga_summary_path = args.output_dir / "ga_summary.json"
    ga_summary_path.write_text(json.dumps({"schemes": summary_rows, "timings_ms": dict(RUN_TIMINGS)}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_candidate_diagnostics(args.output_dir / "candidate_diagnostics.json", CANDIDATE_DIAGNOSTICS, RUN_TIMINGS)
    ml_logger.pipeline_complete(None, {
        "scheme_count": len(summary_rows),
        "total_fragments": sum(len(r) for r in all_item_rows),
        "output_dir": str(args.output_dir), "timings_ms": dict(RUN_TIMINGS),
    })
    return {
        "output_dir": str(args.output_dir), "scheme_count": len(summary_rows),
        "schemes": summary_rows, "item_rows": all_item_rows,
        "ga_summary_path": str(ga_summary_path),
        "candidate_diagnostics_path": str(args.output_dir / "candidate_diagnostics.json"),
        "timings_ms": dict(RUN_TIMINGS),
    }
