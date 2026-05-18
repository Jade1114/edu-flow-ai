from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────

class GenerateSchemeRequest(BaseModel):
    """Parameters mirroring the CLI args of generate_scheme_ga.py."""

    # Task & output
    task_id: Optional[int] = None
    output_dir: str  # absolute path to write scheme CSVs / diagnostics

    # Teaching task filter
    teaching_task_ids: Optional[str] = None  # comma-separated

    # GA hyper-parameters
    variant_count: int = 3
    candidate_pool_size: int = 500
    candidate_top_n: int = 100
    population_size: int = 160
    generations: int = 200
    elite_size: int = 16
    tournament_size: int = 6
    mutation_rate: float = 0.12

    # LightGBM model artifacts
    model_path: str = ""
    schema_path: str = ""

    # Policy
    policy: str = "BALANCED"
    policy_params: Optional[str] = None  # JSON override for POLICY_PROFILES
    generation_config: Optional[str] = None  # JSON from allocation_task_generation_config

    # Fitness weights
    predicted_score_weight: float = 100.0
    rule_score_weight: float = 10.0
    hard_conflict_penalty: float = 100000.0
    teacher_profile_penalty_scale: float = 50.0
    distribution_penalty_scale: float = 5.0
    classroom_stickiness_weight: float = 5.0
    compact_bonus_weight: float = 0.0

    # Runtime
    random_seed: Optional[int] = None
    exclude_weekends: bool = False
    max_tasks: Optional[int] = None
    log_file: Optional[str] = None

    # Teacher penalties payload (JSON string, replaces file-based passing)
    teacher_penalties_json: str  # required: JSON string of teacher penalties


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
