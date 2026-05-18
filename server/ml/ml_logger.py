"""Centralized Python ML service logging.

Separate persistent log files per concern, all under server/ml/logs/:

  ml-service.log        — FastAPI 服务运行日志（请求、错误、启动等）
  ga-algorithm.log      — GA 进化日志（迭代进度、适应度、冲突、耗时）
  lightgbm-training.log — LightGBM 训练日志（参数、迭代结果、特征重要性）
  lightgbm-scoring.log  — LightGBM 评分日志（预测分布、每批次统计）

每个文件使用 RotatingFileHandler，默认 10MB 滚动，保留 5 份。
"""

from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

# ── 路径 ──────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 格式 ──────────────────────────────────────────────────────────────

_DETAILED = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s - %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5


def _logger(name: str, filename: str, level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger(f"ml.{name}")
    log.setLevel(level)
    # Avoid duplicate handlers on re-import
    if log.handlers:
        return log

    handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_DETAILED, _DATE))
    log.addHandler(handler)
    return log


# ── 全局 Logger 实例 ──────────────────────────────────────────────────

service = _logger("service", "ml-service.log")
ga = _logger("ga", "ga-algorithm.log")
training = _logger("training", "lightgbm-training.log")
scoring = _logger("scoring", "lightgbm-scoring.log")


# ── GA 日志结构化封装 ──────────────────────────────────────────────────

def ga_iteration(
    generation: int,
    best_fitness: float,
    hard_conflicts: int,
    candidate_hard_conflicts: int,
    teacher_slot_conflicts: int,
    room_slot_conflicts: int,
    class_slot_conflicts: int,
) -> None:
    """GA 每代迭代日志（只写文件，不写 stdout）。"""
    ga.info(
        "gen=%4d fitness=%8.2f hard=%d cand_hard=%d teacher_slot=%d room_slot=%d class_slot=%d",
        generation, best_fitness, hard_conflicts, candidate_hard_conflicts,
        teacher_slot_conflicts, room_slot_conflicts, class_slot_conflicts,
    )


def ga_summary(metrics: dict[str, Any]) -> None:
    """GA 最优方案总结。"""
    ga.info("GA 最优方案: %s", json.dumps(metrics, ensure_ascii=False, default=str))


def ga_conflict_hotspots(hotspots: dict[str, Any]) -> None:
    """GA 冲突热点。"""
    ga.info("GA 冲突热点: %s", json.dumps(hotspots, ensure_ascii=False, default=str, indent=2))


def ga_pool_diagnostics(diagnostics: dict[str, Any]) -> None:
    """GA 候选池诊断。"""
    ga.info("GA 候选池诊断: %s", json.dumps(diagnostics, ensure_ascii=False, default=str))


# ── LightGBM 评分日志 ─────────────────────────────────────────────────

def scoring_batch(
    task_id: int,
    candidate_count: int,
    score_mean: float,
    score_std: float,
    score_min: float,
    score_max: float,
    model_used: bool,
) -> None:
    """LightGBM 每任务评分批次统计。"""
    source = "LightGBM" if model_used else "rule_score_fallback"
    scoring.info(
        "task=%-6d candidates=%-4d score_mean=%.4f score_std=%.4f min=%.4f max=%.4f source=%s",
        task_id, candidate_count, score_mean, score_std, score_min, score_max, source,
    )


def scoring_summary(total_candidates: int, total_tasks: int) -> None:
    """全局评分汇总。"""
    scoring.info("评分汇总: tasks=%d total_candidates=%d", total_tasks, total_candidates)


# ── LightGBM 训练日志 ─────────────────────────────────────────────────

def training_start(params: dict[str, Any]) -> None:
    """训练开始。"""
    training.info("训练启动: %s", json.dumps(params, ensure_ascii=False, default=str))


def training_iteration(iteration: int, train_metric: float, valid_metric: Optional[float] = None) -> None:
    """训练每轮迭代。"""
    if valid_metric is not None:
        training.info("iter=%4d train=%.6f valid=%.6f", iteration, train_metric, valid_metric)
    else:
        training.info("iter=%4d train=%.6f", iteration, train_metric)


def training_feature_importance(importance: dict[str, float]) -> None:
    """特征重要性。"""
    sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for name, score in sorted_items:
        training.info("  feature=%-40s importance=%.4f", name, score)


def training_complete(metrics: dict[str, Any], model_path: str) -> None:
    """训练完成。"""
    training.info(
        "训练完成: MAE=%.4f RMSE=%.4f R2=%.4f model=%s",
        metrics.get("mae", 0), metrics.get("rmse", 0), metrics.get("r2", 0),
        model_path,
    )


# ── 日志清理 ──────────────────────────────────────────────────────────

def clean_logs(max_age_days: int = 30) -> int:
    """清理超过指定天数的滚动日志文件（非当前文件）。"""
    import time
    now = time.time()
    removed = 0
    for f in LOG_DIR.iterdir():
        if f.suffix in (".log",) and f.name.count(".") > 0:
            age_seconds = now - f.stat().st_mtime
            if age_seconds > max_age_days * 86400:
                f.unlink()
                removed += 1
    return removed
