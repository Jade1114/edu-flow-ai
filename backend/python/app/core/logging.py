"""Logging configuration for the ML service.

Single log file: backend/logs/python.log (no rotation, no backups).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "python.log"

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[3] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def resolve_log_level(name: str, default: int = logging.INFO) -> int:
    raw_level = os.getenv(f"ML_{name.upper()}_LOG_LEVEL") or os.getenv("ML_LOG_LEVEL")
    if not raw_level:
        return default
    normalized = raw_level.strip().upper()
    if normalized.isdigit():
        return int(normalized)
    resolved = getattr(logging, normalized, default)
    return resolved if isinstance(resolved, int) else default


def get_file_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger that writes to the single python.log file."""
    logger = logging.getLogger(f"ml.{name}")
    logger.setLevel(resolve_log_level(name) if level is None else level)
    logger.propagate = False
    if logger.handlers:
        return logger
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    return logger


def get_console_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    logger = logging.getLogger(f"ml.console.{name}")
    logger.setLevel(resolve_log_level(name) if level is None else level)
    logger.propagate = False
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
    logger.addHandler(handler)
    return logger


# ─── 便捷引用 ────────────────────────────────────────
service = get_file_logger("service")
ga = get_file_logger("ga")
training = get_file_logger("training")
scoring = get_file_logger("scoring")
service_console = get_console_logger("service")
