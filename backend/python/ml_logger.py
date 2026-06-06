"""Compatibility facade for Python ML service logging.

New code should import logger construction from ``logging_config`` and business log
helpers from ``log_events``. This module keeps a stable public logging API while
``ml`` is split into smaller modules.
"""

from __future__ import annotations

from .log_events import (
    ga,
    ga_conflict_hotspots,
    ga_iteration,
    ga_pool_diagnostics,
    ga_summary,
    generation_config_parsed,
    pipeline_complete,
    pipeline_start,
    scoring,
    scoring_batch,
    scoring_summary,
    service,
    service_console,
    teacher_profile_summary,
    training,
    training_complete,
    training_feature_importance,
    training_iteration,
    training_start,
)
from .logging_config import LOG_DIR, clean_logs

__all__ = [
    "LOG_DIR",
    "clean_logs",
    "service",
    "service_console",
    "ga",
    "training",
    "scoring",
    "ga_iteration",
    "ga_summary",
    "ga_conflict_hotspots",
    "ga_pool_diagnostics",
    "scoring_batch",
    "scoring_summary",
    "training_start",
    "training_iteration",
    "training_feature_importance",
    "training_complete",
    "pipeline_start",
    "pipeline_complete",
    "teacher_profile_summary",
    "generation_config_parsed",
]
