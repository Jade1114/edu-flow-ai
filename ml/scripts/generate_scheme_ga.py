"""GA + LightGBM scheme generation entry point.

LightGBM scores local scheduling candidates. The genetic algorithm searches complete
scheme combinations globally. Python reads task config from MySQL, writes CSV/JSON
outputs, and Java persists the final result.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import ml_logger
from ml.ga_config import resolve_ga_params
from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    fetch_classrooms,
    fetch_tasks,
    fetch_teacher_profiles,
    fetch_time_slots,
    fetch_allocation_task,
    fetch_generation_config,
    fetch_task_teaching_task_ids,
)
from ml.scheduling.infra.constants import (
    CANDIDATE_DIAGNOSTICS,
    DEFAULT_CANDIDATE_POOL_SIZE,
    DEFAULT_CANDIDATE_TOP_N,
    DEFAULT_CLASSROOM_STICKINESS_WEIGHT,
    DEFAULT_COMPACT_BONUS_WEIGHT,
    DEFAULT_DISTRIBUTION_PENALTY_SCALE,
    DEFAULT_ELITE_SIZE,
    DEFAULT_GENERATIONS,
    DEFAULT_HARD_CONFLICT_PENALTY,
    DEFAULT_MUTATION_RATE,
    DEFAULT_POPULATION_SIZE,
    DEFAULT_PREDICTED_SCORE_WEIGHT,
    DEFAULT_RULE_SCORE_WEIGHT,
    DEFAULT_TEACHER_PROFILE_PENALTY_SCALE,
    DEFAULT_TOURNAMENT_SIZE,
    FEATURE_SCHEMA_PATH,
    MODEL_PATH,
    PROJECT_LOG_DIR,
    TEACHER_PENALTIES_FILENAME,
    TOTAL_WEEKS,
)
from ml.scheduling.infra.generation_config import build_generation_config_json
from ml.scheduling.infra.output import write_schemes_json, write_candidate_diagnostics
from ml.scheduling.infra.runtime import RUN_TIMINGS, log_chain
from ml.scheduling.ga.pipeline import run_ga_pipeline
from ml.scheduling.domain.teacher_penalties import (
    build_teacher_penalties_from_profiles,
    write_teacher_penalties,
)


logger = ml_logger.service


def _resolve_ga_params() -> dict[str, int | float]:
    """Merge ML_GA_PROFILE with per-key environment overrides."""
    from ml.ga_config import resolve_ga_params
    return resolve_ga_params(logger)


def run_ga_pipeline_by_task(
    task_id: int,
    db_config: dict[str, str] | None = None,
    *,
    model_path: Path = MODEL_PATH,
    schema_path: Path = FEATURE_SCHEMA_PATH,
    variant_count: int = 3,
    candidate_pool_size: int | None = None,
    candidate_top_n: int | None = None,
    population_size: int | None = None,
    generations: int | None = None,
    elite_size: int | None = None,
    tournament_size: int | None = None,
    mutation_rate: float | None = None,
    exclude_weekends: bool = False,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Run GA pipeline driven by a task_id — reads everything from DB.

    This is the entry point for the FastAPI async endpoint. Java only needs
    to pass task_id; Python looks up teaching tasks, generation config,
    teacher penalties, etc. from the database directly.
    """
    _env = _resolve_ga_params()
    candidate_pool_size = candidate_pool_size if candidate_pool_size is not None else _env["candidate_pool_size"]
    candidate_top_n = candidate_top_n if candidate_top_n is not None else _env["candidate_top_n"]
    population_size = population_size if population_size is not None else _env["population_size"]
    generations = generations if generations is not None else _env["generations"]
    elite_size = elite_size if elite_size is not None else _env["elite_size"]
    tournament_size = tournament_size if tournament_size is not None else _env["tournament_size"]
    mutation_rate = mutation_rate if mutation_rate is not None else _env["mutation_rate"]

    from datetime import datetime as _dt
    ROOT_DIR = Path(__file__).resolve().parents[1]
    timestamp = _dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    output_dir = ROOT_DIR / "data" / "generated" / f"task_{task_id}_{timestamp}"

    effective_db = db_config or load_db_config()
    with connect(effective_db) as connection:
        log_chain("DB: 查询排课任务", {"task_id": task_id})
        allocation_task = fetch_allocation_task(connection, task_id)
        if allocation_task is None:
            raise ValueError(f"Allocation task {task_id} not found")
        log_chain("DB: 排课任务存在", {"task_id": task_id, "name": allocation_task.get("name")})

        log_chain("DB: 查询教学任务关联", {"task_id": task_id})
        teaching_task_ids = fetch_task_teaching_task_ids(connection, task_id)
        if not teaching_task_ids:
            raise ValueError(f"No teaching tasks bound to allocation task {task_id}")
        log_chain("DB: 教学任务关联", {"task_id": task_id, "teaching_task_count": len(teaching_task_ids)})

        log_chain("DB: 查询生成配置", {"task_id": task_id})
        raw_config = fetch_generation_config(connection, task_id)
        log_chain("DB: 生成配置", {"task_id": task_id, "found": raw_config is not None})

        tasks = fetch_tasks(connection)
        classrooms = fetch_classrooms(connection)
        time_slots = fetch_time_slots(connection)
        teacher_profiles = fetch_teacher_profiles(connection)

    generation_config_json = build_generation_config_json(raw_config) if raw_config else None
    if raw_config and raw_config.get("scheme_count") is not None:
        variant_count = int(raw_config.get("scheme_count"))

    teaching_task_ids_str = ",".join(str(tid) for tid in teaching_task_ids)
    teacher_penalties = build_teacher_penalties_from_profiles(teacher_profiles)
    teacher_penalties_path = output_dir / "teacher_penalties.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_teacher_penalties(teacher_penalties, teacher_penalties_path)

    seed = random_seed if random_seed is not None else int(task_id % 1_000_000)
    args = SimpleNamespace(
        model=model_path, schema=schema_path,
        output=output_dir / "scheme_001.csv", output_dir=output_dir,
        max_tasks=None, variant_count=variant_count, random_seed=seed,
        generation_config=generation_config_json,
        teacher_penalties=teacher_penalties_path,
        teaching_task_ids=teaching_task_ids_str,
        start_week=None, end_week=None, exclude_weekends=exclude_weekends,
        candidate_pool_size=candidate_pool_size, candidate_top_n=candidate_top_n,
        population_size=population_size, generations=generations,
        elite_size=elite_size, tournament_size=tournament_size,
        mutation_rate=mutation_rate,
        predicted_score_weight=DEFAULT_PREDICTED_SCORE_WEIGHT,
        rule_score_weight=DEFAULT_RULE_SCORE_WEIGHT,
        hard_conflict_penalty=DEFAULT_HARD_CONFLICT_PENALTY,
        teacher_profile_penalty_scale=50.0, distribution_penalty_scale=5.0,
        classroom_stickiness_weight=5.0, compact_bonus_weight=0.0,
        log_file=PROJECT_LOG_DIR / "ga-runs" / f"{output_dir.name}.log",
    )
    result = run_ga_pipeline(args)

    log_chain("Pipeline 按任务调度完成", {
        "task_id": task_id,
        "scheme_count": len(result.get("schemes", [])),
        "output_dir": str(output_dir),
    })
    ml_logger.pipeline_complete(task_id, {
        "scheme_count": len(result.get("schemes", [])),
        "output_dir": str(output_dir),
        "timings_ms": dict(RUN_TIMINGS),
    })
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scheduling schemes with GA + LightGBM.")
    parser.add_argument("--task-id", type=int, default=None, help="Allocation task ID (reads from DB).")
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--schema", type=Path, default=FEATURE_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--variant-count", type=int, default=3)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--generation-config", type=str, default=None)
    parser.add_argument("--teacher-penalties", type=Path, default=None)
    parser.add_argument("--teaching-task-ids", type=str, default=None)
    parser.add_argument("--start-week", type=int, default=None)
    parser.add_argument("--end-week", type=int, default=None)
    parser.add_argument("--exclude-weekends", action="store_true")
    parser.add_argument("--candidate-pool-size", type=int, default=DEFAULT_CANDIDATE_POOL_SIZE)
    parser.add_argument("--candidate-top-n", type=int, default=DEFAULT_CANDIDATE_TOP_N)
    parser.add_argument("--population-size", type=int, default=DEFAULT_POPULATION_SIZE)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--elite-size", type=int, default=DEFAULT_ELITE_SIZE)
    parser.add_argument("--tournament-size", type=int, default=DEFAULT_TOURNAMENT_SIZE)
    parser.add_argument("--mutation-rate", type=float, default=DEFAULT_MUTATION_RATE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.task_id is not None:
        result = run_ga_pipeline_by_task(task_id=args.task_id)
        print(f"Pipeline result: {json.dumps(result.get('schemes', []), ensure_ascii=False)}")
        return
    result = run_ga_pipeline(args)
    print(f"Pipeline result: {json.dumps(result.get('schemes', []), ensure_ascii=False)}" if result.get("schemes") else "No schemes generated.")


if __name__ == "__main__":
    main()
