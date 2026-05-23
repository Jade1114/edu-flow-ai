"""Runtime logging and timing state for scheduling pipelines."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from ml import ml_logger
from ml.scheduling.infra.constants import LOG_PREFIX

PYTHON_LOG_FILE: Path | None = None
RUN_TIMINGS: dict[str, float] = defaultdict(float)


def configure_python_log(log_file: Path | None) -> None:
    global PYTHON_LOG_FILE
    PYTHON_LOG_FILE = log_file
    if PYTHON_LOG_FILE is not None:
        PYTHON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        PYTHON_LOG_FILE.write_text("", encoding="utf-8")


def add_timing(name: str, started_at: float) -> None:
    RUN_TIMINGS[name] += round((perf_counter() - started_at) * 1000, 3)


def log_chain(message: str, payload: Any | None = None) -> None:
    if payload is None:
        line = f"{LOG_PREFIX} {message}"
    else:
        line = f"{LOG_PREFIX} {message}: {json.dumps(payload, ensure_ascii=False, default=str)}"
    print(line, flush=True)
    if PYTHON_LOG_FILE is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with PYTHON_LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {line}\n")
    ml_logger.service.info("%s %s", LOG_PREFIX, line)
