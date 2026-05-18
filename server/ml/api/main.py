from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ml_logger

from .routers import ga, health, training

ML_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — store ml_dir in app.state."""
    app.state.ml_dir = ML_DIR
    ml_logger.service.info("ML service started, ml_dir=%s", ML_DIR)
    yield
    ml_logger.service.info("ML service shutting down")


app = FastAPI(
    title="Edu-Flow-AI ML Service",
    description="Python-side scheduling pipeline: GA + LightGBM for scheme generation and training.",
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
    started_at = __import__("time").time()
    response = await call_next(request)
    elapsed_ms = round((__import__("time").time() - started_at) * 1000, 1)
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
app.include_router(ga.router, prefix="/api/ml", tags=["ga"])
app.include_router(training.router, prefix="/api/ml", tags=["training"])
