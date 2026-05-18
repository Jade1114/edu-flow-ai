from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    ml_dir: Path = request.app.state.ml_dir
    model_path = ml_dir / "models" / "schedule_ranker_v1.txt"
    return HealthResponse(
        status="ok",
        lightgbm_available=model_path.exists(),
        model_path=str(model_path) if model_path.exists() else None,
        ml_dir=str(ml_dir),
    )
