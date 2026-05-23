from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from ml import ml_logger
from ml.ga_config import collect_ga_env_overrides, resolve_ga_params, resolve_ga_profile_name

# Load .env so ML_GA_PROFILE etc. are picked up from file
# Python doesn't auto-read .env like Spring does
_dotenv_loaded = False
try:
    from dotenv import load_dotenv
    _env_candidates = [
        Path(__file__).resolve().parents[3] / ".env",   # project root .env
    ]
    for _env_path in _env_candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
            _dotenv_loaded = True
except ImportError:
    pass

from ml.api.routers import ga, health, training

ML_DIR = Path(__file__).resolve().parents[1]

# ── GA 预设 ─────────────────────────────────────────────────────────


def _log_ga_profile():
    """Read ML_GA_PROFILE env and log the resolved parameters."""
    profile = resolve_ga_profile_name(ml_logger.service)
    params = resolve_ga_params(ml_logger.service)
    overrides = collect_ga_env_overrides(ml_logger.service)
    base = (
        f"ML_GA_PROFILE={profile} | population={params['population_size']}"
        f" generations={params['generations']} candidate_top_n={params['candidate_top_n']}"
        f" elite={params['elite_size']} tournament={params['tournament_size']}"
        f" mutation={params['mutation_rate']:.2f}"
    )
    extra = f" +overrides: {overrides}" if overrides else ""
    ml_logger.service.info("%s%s", base, extra)
    ml_logger.service_console.info("%s%s", base, extra)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — store ml_dir in app.state."""
    app.state.ml_dir = ML_DIR

    _log_ga_profile()
    ml_logger.service.info("ML service started, ml_dir=%s", ML_DIR)
    ml_logger.service_console.info("ML service started, ml_dir=%s", ML_DIR)
    yield
    ml_logger.service.info("ML service shutting down")
    ml_logger.service_console.info("ML service shutting down")


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
app.include_router(ga.router, prefix="/api/ml", tags=["ga"])
app.include_router(training.router, prefix="/api/ml", tags=["training"])
