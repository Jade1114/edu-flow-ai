"""V3 scheduling-chain endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml.scheduling_v3.placement_candidates import generate_placement_candidates_jsonl
from ml.scheduling_v3.plan_templates import generate_task_plans_jsonl
from ml.scheduling_v3.pipeline import run_v3_pipeline

router = APIRouter(tags=["v3"])


class PlacementCandidatesRequest(BaseModel):
    task_id: int
    top_k: int = Field(default=30, ge=1, le=50)
    raw_top_k: int = Field(default=200, ge=1, le=5000)
    room_pool_limit: int = Field(default=80, ge=1, le=500)
    diversity_rerank: bool = True
    max_per_room: int = Field(default=2, ge=1, le=50)
    max_per_slot: int = Field(default=3, ge=1, le=50)
    predict_batch_size: int = Field(default=100000, ge=1000, le=1000000)


class TaskPlansRequest(BaseModel):
    candidates_path: str
    plan_count: int = Field(default=8, ge=1, le=50)
    output_dir: str | None = None


@router.post("/v3/placement-candidates")
async def generate_placement_candidates(request: PlacementCandidatesRequest):
    """Generate one JSONL row per teaching task with TopK placement resources."""

    try:
        return generate_placement_candidates_jsonl(
            request.task_id,
            top_k=request.top_k,
            raw_top_k=request.raw_top_k,
            room_pool_limit=request.room_pool_limit,
            diversity_rerank=request.diversity_rerank,
            max_per_room=request.max_per_room,
            max_per_slot=request.max_per_slot,
            predict_batch_size=request.predict_batch_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/v3/task-plans")
async def generate_task_plans(request: TaskPlansRequest):
    """Generate stable local plan templates from V3 placement candidates."""

    try:
        return generate_task_plans_jsonl(
            request.candidates_path,
            plan_count=request.plan_count,
            output_dir=request.output_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class GenerateV3Request(BaseModel):
    allocation_task_id: int
    top_k: int = Field(default=10, ge=1, le=50)
    plan_count: int = Field(default=8, ge=1, le=50)
    output_dir: str | None = None


@router.post("/v3/generate")
async def generate_v3(request: GenerateV3Request):
    """Run full V3 pipeline: placement → templates → teacher groups → schedule.

    Professional courses only (pre-filtered teaching tasks required).
    """
    try:
        return run_v3_pipeline(
            allocation_task_id=request.allocation_task_id,
            top_k=request.top_k,
            plan_count=request.plan_count,
            output_dir=request.output_dir,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
