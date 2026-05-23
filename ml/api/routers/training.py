"""Training endpoint — trigger LightGBM training from feedback data."""

from __future__ import annotations

import importlib

from fastapi import APIRouter, Request

from ml.api.schemas import TrainRequest, TrainResponse

router = APIRouter(tags=["training"])


@router.post("/train", response_model=TrainResponse)
async def train(req: TrainRequest, _request: Request) -> TrainResponse:
    try:
        train_lightgbm = importlib.import_module("ml.scripts.train_lightgbm")
        result = train_lightgbm.run_training_pipeline(
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
