from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────

class GenerateSchemeRequest(BaseModel):
    """Simple request — Python reads everything from DB via task_id."""
    task_id: int
    output_dir: str  # absolute path to write scheme CSVs / diagnostics


class TrainRequest(BaseModel):
    """Trigger LightGBM training from feedback data."""
    training_data_dir: str = ""
    output_model_path: str = ""
    output_schema_path: str = ""
    training_params: dict[str, Any] = Field(default_factory=dict)


# ── Response Models ─────────────────────────────────────────────────

class SchemeInfo(BaseModel):
    scheme_no: int
    output_path: str
    tasks: int = 0
    expected_fragments: int = 0
    generated_fragments: int = 0
    hard_conflict_fragments: int = 0
    avg_predicted_score: float = 0.0
    avg_rule_score: float = 0.0
    fitness: Optional[float] = None
    hard_conflict_count: Optional[int] = None
    candidate_hard_conflict_count: Optional[int] = None
    teacher_slot_conflict_count: Optional[int] = None
    room_slot_conflict_count: Optional[int] = None
    class_slot_conflict_count: Optional[int] = None
    teacher_profile_penalty_total: Optional[float] = None
    distribution_penalty: Optional[float] = None
    classroom_switches: Optional[int] = None
    candidate_pool_count: Optional[int] = None


class GenerateSchemeResponse(BaseModel):
    success: bool
    output_dir: str
    scheme_count: int
    schemes: list[SchemeInfo]
    ga_summary_path: str
    candidate_diagnostics_path: str
    timings_ms: dict[str, float]
    error: Optional[str] = None


# ── Async Task Models ──────────────────────────────────────────────

class TaskInfo(BaseModel):
    task_id: str
    name: str
    status: str
    progress: int
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskStatusResponse(BaseModel):
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
