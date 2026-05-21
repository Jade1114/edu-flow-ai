from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ml_logger

# Load .env so ML_GA_PROFILE etc. are picked up from file
# Python doesn't auto-read .env like Spring does
_dotenv_loaded = False
try:
    from dotenv import load_dotenv
    _env_candidates = [
        Path(__file__).resolve().parents[2] / ".env",   # server/.env
        Path(__file__).resolve().parents[3] / ".env",   # project root .env
    ]
    for _env_path in _env_candidates:
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
            _dotenv_loaded = True
except ImportError:
    pass

try:
    from .routers import ga, health, training
except ImportError:
    from routers import ga, health, training

ML_DIR = Path(__file__).resolve().parents[1]

# ── GA 预设（与 generate_scheme_ga.py 同步） ────────────────────

_GA_PROFILES = {
    "fast": {"population_size": 60, "generations": 60, "candidate_top_n": 40, "elite_size": 6, "tournament_size": 4, "mutation_rate": 0.10, "candidate_pool_size": 500},
    "default": {"population_size": 100, "generations": 100, "candidate_top_n": 60, "elite_size": 10, "tournament_size": 5, "mutation_rate": 0.10, "candidate_pool_size": 500},
    "quality": {"population_size": 160, "generations": 200, "candidate_top_n": 100, "elite_size": 16, "tournament_size": 6, "mutation_rate": 0.12, "candidate_pool_size": 500},
}
_GA_KEYS = list(next(iter(_GA_PROFILES.values())))


def _log_ga_profile():
    """Read ML_GA_PROFILE env and log the resolved parameters."""
    import os
    profile = os.environ.get("ML_GA_PROFILE", "default").strip().lower()
    if profile not in _GA_PROFILES:
        profile = "default"
    params = _GA_PROFILES[profile]
    overrides = {}
    for k in _GA_KEYS:
        env_val = os.environ.get(f"ML_GA_{k.upper()}")
        if env_val is not None and env_val.strip():
            overrides[k] = int(env_val) if k != "mutation_rate" else float(env_val)
    base = (f"ML_GA_PROFILE={profile} | population={params['population_size']}"
            f" generations={params['generations']} candidate_top_n={params['candidate_top_n']}"
            f" elite={params['elite_size']} tournament={params['tournament_size']}"
            f" mutation={params['mutation_rate']:.2f}")
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
