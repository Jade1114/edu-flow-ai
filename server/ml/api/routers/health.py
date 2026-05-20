from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

import ml_logger

try:
    from ..schemas import HealthResponse
except ImportError:
    from schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    ml_dir: Path = request.app.state.ml_dir
    feedback_model_path = ml_dir / "models" / "feedback" / "current" / "schedule_ranker.txt"
    base_model_path = ml_dir / "models" / "base" / "schedule_ranker_v1.txt"
    model_path = feedback_model_path if feedback_model_path.exists() else base_model_path
    available = model_path.exists()
    ml_logger.service.debug("Health check: lightgbm=%s model=%s", available, model_path)
    return HealthResponse(
        status="ok",
        lightgbm_available=available,
        model_path=str(model_path) if available else None,
        ml_dir=str(ml_dir),
    )
