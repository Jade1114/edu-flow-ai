from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────

class GenerateSchemeRequest(BaseModel):
    """Minimal request — just task_id, Python reads everything from DB."""
    task_id: int


class TrainRequest(BaseModel):
    """Trigger LightGBM training from feedback data."""
    training_data_dir: str = ""
    output_model_path: str = ""
    output_schema_path: str = ""
    training_params: dict[str, Any] = Field(default_factory=dict)


# ── Async Task Models ──────────────────────────────────────────────

class TaskStatusResponse(BaseModel):
    """Response for polling async GA task status."""
    task_id: str
    status: str
    progress: int = 0
    error: Optional[str] = None
    result: Optional[Any] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Other Service Models ────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    lightgbm_available: bool
    model_path: Optional[str] = None
    ml_dir: str


class TrainResponse(BaseModel):
    success: bool
    model_path: Optional[str] = None
    schema_path: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None
