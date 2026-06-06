from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from python import ml_logger

# Load .env so ML service settings are picked up from file
# Python doesn't auto-read .env like Spring does
_dotenv_loaded = False
try:
    from dotenv import load_dotenv
    _env_candidates = [
        Path(__file__).resolve().parents[2] / ".env",   # project root .env
    ]
    for _env_path in _env_candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
            _dotenv_loaded = True
except ImportError:
    pass

from python.api.routers import health, v3

ML_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — store ml_dir in app.state."""
    app.state.ml_dir = ML_DIR
    ml_logger.service.info("ML service started, ml_dir=%s", ML_DIR)
    ml_logger.service_console.info("ML service started, ml_dir=%s", ML_DIR)
    yield
    ml_logger.service.info("ML service shutting down")
    ml_logger.service_console.info("ML service shutting down")


app = FastAPI(
    title="Edu-Flow-AI ML Service",
    description="Edu-Flow-AI V3 scheduling pipeline: Placement Model + CP-SAT Global Plan Selector.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Middleware ────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - started_at) * 1000, 1)
    ml_logger.service.info(
        "%s %s → %s (%sms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ── Routers ──────────────────────────────────────────────────────────

app.include_router(health.router, prefix="/api/ml", tags=["health"])
app.include_router(v3.router, prefix="/api/ml", tags=["v3"])
