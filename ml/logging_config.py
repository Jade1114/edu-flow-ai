"""Logging configuration for the Python ML service.

This module owns logger construction only. Business-specific logging helpers live in
``log_events.py`` so logging setup stays easy to review and reuse.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "python"
LOG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[1] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

DETAILED_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s - %(message)s"
CONSOLE_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

LOG_FILES = {
    "service": "ml-service.log",
    "ga": "ga-algorithm.log",
    "training": "lightgbm-training.log",
    "scoring": "lightgbm-scoring.log",
}


def resolve_log_level(name: str, default: int = logging.INFO) -> int:
    """Resolve logger level from env, supporting global and per-logger overrides."""
    raw_level = os.getenv(f"ML_{name.upper()}_LOG_LEVEL") or os.getenv("ML_LOG_LEVEL")
    if not raw_level:
        return default

    normalized = raw_level.strip().upper()
    if normalized.isdigit():
        return int(normalized)

    resolved = getattr(logging, normalized, default)
    return resolved if isinstance(resolved, int) else default


def get_file_logger(name: str, filename: str, level: Optional[int] = None) -> logging.Logger:
    """Return an ``ml.<name>`` logger backed by a rotating UTF-8 file handler."""
    logger = logging.getLogger(f"ml.{name}")
    logger.setLevel(resolve_log_level(name) if level is None else level)
    logger.propagate = False

    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(DETAILED_FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    return logger


def get_console_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return an ``ml.console.<name>`` logger backed by stderr/stdout stream output."""
    logger = logging.getLogger(f"ml.console.{name}")
    logger.setLevel(resolve_log_level(name) if level is None else level)
    logger.propagate = False

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    return logger


def clean_logs(max_age_days: int = 30) -> int:
    """Remove rotated log files older than ``max_age_days`` while keeping active logs."""
    import time

    now = time.time()
    max_age_seconds = max_age_days * 86400
    active_names = set(LOG_FILES.values())
    rotated_prefixes = tuple(f"{name}." for name in active_names)
    removed = 0

    for file_path in LOG_DIR.iterdir():
        if not file_path.is_file():
            continue
        if file_path.name in active_names:
            continue
        if not file_path.name.startswith(rotated_prefixes):
            continue
        if now - file_path.stat().st_mtime <= max_age_seconds:
            continue

        file_path.unlink()
        removed += 1

    return removed
