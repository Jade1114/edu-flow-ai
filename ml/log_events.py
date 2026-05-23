"""Business-level logging helpers for Python ML workflows."""

from __future__ import annotations

import json
from typing import Any, Optional

from .logging_config import LOG_FILES, get_console_logger, get_file_logger

service = get_file_logger("service", LOG_FILES["service"])
service_console = get_console_logger("service")
ga = get_file_logger("ga", LOG_FILES["ga"])
training = get_file_logger("training", LOG_FILES["training"])
scoring = get_file_logger("scoring", LOG_FILES["scoring"])


def _json(data: Any, *, indent: Optional[int] = None) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, indent=indent)


def ga_iteration(
    generation: int,
    best_fitness: float,
    hard_conflicts: int,
    candidate_hard_conflicts: int,
    teacher_slot_conflicts: int,
    room_slot_conflicts: int,
    class_slot_conflicts: int,
) -> None:
    """Log one GA generation summary to file only."""
    ga.info(
        "gen=%4d fitness=%8.2f hard=%d cand_hard=%d teacher_slot=%d room_slot=%d class_slot=%d",
        generation,
        best_fitness,
        hard_conflicts,
        candidate_hard_conflicts,
        teacher_slot_conflicts,
        room_slot_conflicts,
        class_slot_conflicts,
    )


def ga_summary(metrics: dict[str, Any]) -> None:
    """Log the best GA scheme summary."""
    ga.info("GA 最优方案: %s", _json(metrics))


def ga_conflict_hotspots(hotspots: dict[str, Any]) -> None:
    """Log GA conflict hotspots."""
    ga.info("GA 冲突热点: %s", _json(hotspots, indent=2))


def ga_pool_diagnostics(diagnostics: dict[str, Any]) -> None:
    """Log GA candidate-pool diagnostics."""
    ga.info("GA 候选池诊断: %s", _json(diagnostics))


def scoring_batch(
    task_id: int,
    candidate_count: int,
    score_mean: float,
    score_std: float,
    score_min: float,
    score_max: float,
    model_used: bool,
) -> None:
    """Log LightGBM scoring statistics for one task batch."""
    source = "LightGBM" if model_used else "rule_score_fallback"
    scoring.info(
        "task=%-6d candidates=%-4d score_mean=%.4f score_std=%.4f min=%.4f max=%.4f source=%s",
        task_id,
        candidate_count,
        score_mean,
        score_std,
        score_min,
        score_max,
        source,
    )


def scoring_summary(total_candidates: int, total_tasks: int) -> None:
    """Log global scoring summary."""
    scoring.info("评分汇总: tasks=%d total_candidates=%d", total_tasks, total_candidates)


def training_start(params: dict[str, Any]) -> None:
    """Log training startup parameters."""
    training.info("训练启动: %s", _json(params))


def training_iteration(iteration: int, train_metric: float, valid_metric: Optional[float] = None) -> None:
    """Log one training iteration metric row."""
    if valid_metric is not None:
        training.info("iter=%4d train=%.6f valid=%.6f", iteration, train_metric, valid_metric)
    else:
        training.info("iter=%4d train=%.6f", iteration, train_metric)


def training_feature_importance(importance: dict[str, float]) -> None:
    """Log feature importance in descending order."""
    sorted_items = sorted(importance.items(), key=lambda item: item[1], reverse=True)
    for name, score in sorted_items:
        training.info("  feature=%-40s importance=%.4f", name, score)


def training_complete(metrics: dict[str, Any], model_path: str) -> None:
    """Log training completion metrics."""
    training.info(
        "训练完成: MAE=%.4f RMSE=%.4f R2=%.4f model=%s",
        metrics.get("mae", 0),
        metrics.get("rmse", 0),
        metrics.get("r2", 0),
        model_path,
    )


def pipeline_start(task_id: int | None, config: dict[str, Any]) -> None:
    """Log scheduling pipeline startup."""
    service.info("PIPELINE_START task_id=%s config=%s", task_id, _json(config))


def pipeline_complete(task_id: int | None, summary: dict[str, Any]) -> None:
    """Log scheduling pipeline completion."""
    service.info("PIPELINE_COMPLETE task_id=%s summary=%s", task_id, _json(summary))


def teacher_profile_summary(teacher_count: int, penalty_summary: dict[str, Any]) -> None:
    """Log teacher-profile penalty summary."""
    service.info("TEACHER_PROFILE teacher_count=%d summary=%s", teacher_count, _json(penalty_summary))


def generation_config_parsed(config: dict[str, Any]) -> None:
    """Log parsed generation config."""
    service.info("GENERATION_CONFIG %s", _json(config))
