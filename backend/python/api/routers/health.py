from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from python import ml_logger
from python.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    ml_dir: Path = request.app.state.ml_dir
    model_path = ml_dir.parent / "models" / "v3" / "placement_direct_model.txt"
    available = model_path.exists()
    ml_logger.service.debug("Health check: V3 model=%s available=%s", model_path, available)
    return HealthResponse(
        status="ok",
        lightgbm_available=available,
        model_path=str(model_path) if available else None,
        ml_dir=str(ml_dir),
    )
