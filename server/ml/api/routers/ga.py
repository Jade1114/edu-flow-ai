"""GA scheme generation endpoint.

Replicates generate_scheme_ga.main() logic but receives params via HTTP body.
Teacher penalties arrive inline as JSON, no need for a pre-written file.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..schemas import GenerateSchemeRequest, GenerateSchemeResponse, SchemeInfo

router = APIRouter(tags=["ga"])


def _import_ga() -> Any:
    ml_dir = Path(__file__).resolve().parents[2]
    scripts_dir = str(ml_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import generate_scheme_ga  # noqa: F811

    return generate_scheme_ga


def _write_teacher_penalties(penalties_json: str, output_path: Path) -> None:
    """Write teacher penalties JSON to disk for load_teacher_penalties()."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(penalties_json, encoding="utf-8")


@router.post("/generate-scheme", response_model=GenerateSchemeResponse)
async def generate_scheme(req: GenerateSchemeRequest, _request: Request) -> GenerateSchemeResponse:
    ga = _import_ga()

    # Resolve paths
    ml_dir = Path(_request.app.state.ml_dir)
    output_dir = Path(req.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = Path(req.model_path) if req.model_path else ml_dir / "models" / "schedule_ranker_v1.txt"
    schema_path = Path(req.schema_path) if req.schema_path else ml_dir / "data" / "feature_schema.json"
    teacher_penalties_path = output_dir / "teacher_penalties.json"
    log_file = Path(req.log_file) if req.log_file else output_dir / "python-ga.log"

    # Write teacher penalties to disk (the pipeline expects a file path)
    _write_teacher_penalties(req.teacher_penalties_json, teacher_penalties_path)

    # Build a namespace that mirrors argparse output
    random_seed = req.random_seed if req.random_seed is not None else 42
    args = Namespace(
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

    # Run the pipeline
    try:
        result = ga.run_ga_pipeline(args)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GA pipeline failed: {exc}") from exc

    # Convert result dict to response model
    schemes = []
    for s in result.get("schemes", []):
        schemes.append(SchemeInfo(
            scheme_no=s.get("scheme_no", 0),
            output_path=str(s.get("output_path", "")),
            tasks=s.get("tasks", 0),
            expected_fragments=s.get("expected_fragments", 0),
            generated_fragments=s.get("generated_fragments", 0),
            hard_conflict_fragments=s.get("hard_conflict_fragments", 0),
            avg_predicted_score=s.get("avg_predicted_score", 0.0),
            avg_rule_score=s.get("avg_rule_score", 0.0),
            fitness=s.get("fitness"),
            hard_conflict_count=s.get("hard_conflict_count"),
            candidate_hard_conflict_count=s.get("candidate_hard_conflict_count"),
            teacher_slot_conflict_count=s.get("teacher_slot_conflict_count"),
            room_slot_conflict_count=s.get("room_slot_conflict_count"),
            class_slot_conflict_count=s.get("class_slot_conflict_count"),
            teacher_profile_penalty_total=s.get("teacher_profile_penalty_total"),
            distribution_penalty=s.get("distribution_penalty"),
            classroom_switches=s.get("classroom_switches"),
            candidate_pool_count=s.get("candidate_pool_count"),
        ))

    return GenerateSchemeResponse(
        success=True,
        output_dir=result.get("output_dir", str(output_dir)),
        scheme_count=result.get("scheme_count", 0),
        schemes=schemes,
        ga_summary_path=result.get("ga_summary_path", ""),
        candidate_diagnostics_path=result.get("candidate_diagnostics_path", ""),
        timings_ms=result.get("timings_ms", {}),
    )
