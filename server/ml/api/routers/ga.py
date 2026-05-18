"""GA scheme generation endpoints — async task pattern.

POST  /api/ml/generate-scheme   → 202 Accepted + task_id (background GA run)
GET   /api/ml/generate-scheme/{task_id}  → task status + result when done
"""

from __future__ import annotations

import asyncio
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import ml_logger

from .. import task_store
from ..schemas import GenerateSchemeRequest, TaskInfo, TaskStatusResponse

router = APIRouter(tags=["ga"])


def _import_ga() -> Any:
    ml_dir = Path(__file__).resolve().parents[2]
    scripts_dir = str(ml_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import generate_scheme_ga  # noqa: F811

    return generate_scheme_ga


def _build_args(
    req: GenerateSchemeRequest,
    ml_dir: Path,
    output_dir: Path,
) -> Namespace:
    """Build argparse Namespace mirroring generate_scheme_ga.py CLI args."""
    model_path = Path(req.model_path) if req.model_path else ml_dir / "models" / "schedule_ranker_v1.txt"
    schema_path = Path(req.schema_path) if req.schema_path else ml_dir / "data" / "feature_schema.json"
    teacher_penalties_path = output_dir / "teacher_penalties.json"
    log_file = Path(req.log_file) if req.log_file else output_dir / "python-ga.log"

    # Write teacher penalties to disk
    teacher_penalties_path.parent.mkdir(parents=True, exist_ok=True)
    teacher_penalties_path.write_text(req.teacher_penalties_json, encoding="utf-8")

    random_seed = req.random_seed if req.random_seed is not None else 42
    return Namespace(
        model=model_path,
        schema=schema_path,
        output=output_dir / "scheme_001.csv",
        output_dir=output_dir,
        max_tasks=req.max_tasks,
        variant_count=req.variant_count,
        random_seed=random_seed,
        policy=req.policy,
        policy_params=req.policy_params,
        generation_config=req.generation_config,
        teacher_penalties=teacher_penalties_path,
        teaching_task_ids=req.teaching_task_ids,
        start_week=None,
        end_week=None,
        exclude_weekends=req.exclude_weekends,
        candidate_pool_size=req.candidate_pool_size,
        candidate_top_n=req.candidate_top_n,
        population_size=req.population_size,
        generations=req.generations,
        elite_size=req.elite_size,
        tournament_size=req.tournament_size,
        mutation_rate=req.mutation_rate,
        predicted_score_weight=req.predicted_score_weight,
        rule_score_weight=req.rule_score_weight,
        hard_conflict_penalty=req.hard_conflict_penalty,
        teacher_profile_penalty_scale=req.teacher_profile_penalty_scale,
        distribution_penalty_scale=req.distribution_penalty_scale,
        classroom_stickiness_weight=req.classroom_stickiness_weight,
        compact_bonus_weight=req.compact_bonus_weight,
        log_file=log_file,
    )


def _run_pipeline(args: Namespace) -> dict[str, Any]:
    """Blocking wrapper — runs GA pipeline, called in thread pool."""
    ga = _import_ga()
    return ga.run_ga_pipeline(args)


@router.post("/generate-scheme", status_code=202)
async def submit_generate_scheme(
    req: GenerateSchemeRequest,
    request: Request,
) -> JSONResponse:
    """Submit a GA scheme generation task. Returns immediately with a task_id.

    Poll GET /api/ml/generate-scheme/{task_id} for the result.
    """
    ml_dir: Path = request.app.state.ml_dir
    output_dir = Path(req.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    args = _build_args(req, ml_dir, output_dir)

    # Create async task
    task_id = task_store.create(
        name=f"GA scheme generation → {output_dir.name}",
        total_steps=100,
    )

    ml_logger.service.info(
        "GA task submitted: task_id=%s output_dir=%s variant_count=%d policy=%s",
        task_id, req.output_dir, req.variant_count, req.policy,
    )

    # Fire & forget in thread pool (non-blocking for FastAPI event loop)
    asyncio.create_task(task_store.run_blocking(task_id, _run_pipeline, args))

    return JSONResponse(
        content={
            "task_id": task_id,
            "status_url": f"/api/ml/generate-scheme/{task_id}",
            "status": task_store.get(task_id)["status"],
            "message": "GA generation submitted, poll status_url for result",
        },
        status_code=202,
    )


@router.get("/generate-scheme/{task_id}", response_model=TaskStatusResponse)
async def get_generate_scheme_status(task_id: str) -> TaskStatusResponse:
    """Poll task status. Returns result once the GA pipeline finishes."""
    try:
        task = task_store.get(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        error=task.get("error"),
        result=task.get("result"),
        created_at=task.get("created_at"),
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
    )
