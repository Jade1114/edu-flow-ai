"""Shared GA profile presets and environment override parsing."""

from __future__ import annotations

import logging
import os

GA_PROFILES: dict[str, dict[str, int | float]] = {
    "fast": {
        "candidate_pool_size": 500,
        "candidate_top_n": 40,
        "population_size": 60,
        "generations": 60,
        "elite_size": 6,
        "tournament_size": 4,
        "mutation_rate": 0.10,
    },
    "default": {
        "candidate_pool_size": 500,
        "candidate_top_n": 60,
        "population_size": 100,
        "generations": 100,
        "elite_size": 10,
        "tournament_size": 5,
        "mutation_rate": 0.10,
    },
    "quality": {
        "candidate_pool_size": 500,
        "candidate_top_n": 100,
        "population_size": 160,
        "generations": 200,
        "elite_size": 16,
        "tournament_size": 6,
        "mutation_rate": 0.12,
    },
}

ENV_GA_KEYS = tuple(next(iter(GA_PROFILES.values())).keys())


def resolve_ga_profile_name(logger: logging.Logger | None = None) -> str:
    """Return a known GA profile name from ``ML_GA_PROFILE``."""
    profile = os.environ.get("ML_GA_PROFILE", "default").strip().lower()
    if profile in GA_PROFILES:
        return profile

    if logger is not None:
        logger.warning("Unknown ML_GA_PROFILE=%r, falling back to 'default'", profile)
    return "default"


def resolve_ga_params(logger: logging.Logger | None = None) -> dict[str, int | float]:
    """Merge GA profile presets with per-key ``ML_GA_*`` environment overrides."""
    profile = resolve_ga_profile_name(logger)
    params: dict[str, int | float] = dict(GA_PROFILES[profile])

    for key in ENV_GA_KEYS:
        env_val = os.environ.get(f"ML_GA_{key.upper()}")
        if env_val is None or not env_val.strip():
            continue

        try:
            params[key] = int(env_val) if key != "mutation_rate" else float(env_val)
        except ValueError:
            if logger is not None:
                logger.warning("Invalid ML_GA_%s=%r, ignoring", key.upper(), env_val)

    return params


def collect_ga_env_overrides(logger: logging.Logger | None = None) -> dict[str, int | float]:
    """Return valid explicit GA env overrides for startup logging."""
    overrides: dict[str, int | float] = {}
    for key in ENV_GA_KEYS:
        env_val = os.environ.get(f"ML_GA_{key.upper()}")
        if env_val is None or not env_val.strip():
            continue
        try:
            overrides[key] = int(env_val) if key != "mutation_rate" else float(env_val)
        except ValueError:
            if logger is not None:
                logger.warning("Invalid ML_GA_%s=%r, ignoring", key.upper(), env_val)
    return overrides
