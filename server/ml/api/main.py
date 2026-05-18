from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ga, health, training

ML_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — store ml_dir in app.state."""
    app.state.ml_dir = ML_DIR
    yield


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

# ── Routers ──────────────────────────────────────────────────────────

app.include_router(health.router, prefix="/api/ml", tags=["health"])
app.include_router(ga.router, prefix="/api/ml", tags=["ga"])
app.include_router(training.router, prefix="/api/ml", tags=["training"])
