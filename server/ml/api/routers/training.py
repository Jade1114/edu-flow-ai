"""Training endpoint — trigger LightGBM training from feedback data."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import Request

from ..schemas import TrainRequest, TrainResponse

router = APIRouter(tags=["training"])


def _import_module(module_name: str) -> Any:
    ml_dir = Path(__file__).resolve().parents[2]
    scripts_dir = str(ml_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return __import__(module_name)


@router.post("/train", response_model=TrainResponse)
async def train(req: TrainRequest, _request: Request) -> TrainResponse:
    try:
        train_lgb = _import_module("train_lightgbm")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to import train_lightgbm: {exc}") from exc

    try:
        result = train_lgb.run_training_pipeline(
            training_data_dir=req.training_data_dir or None,
            output_model_path=req.output_model_path or None,
            output_schema_path=req.output_schema_path or None,
            **req.training_params,
        )
    except Exception as exc:
        return TrainResponse(success=False, error=str(exc))

    return TrainResponse(
        success=True,
        model_path=result.get("model_path"),
        schema_path=result.get("schema_path"),
        metrics=result.get("metrics"),
    )
