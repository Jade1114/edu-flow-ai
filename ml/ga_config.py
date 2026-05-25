"""GA runtime parameter presets."""

from __future__ import annotations
import os


GA_PROFILES = {
    # Fast keeps validation runs short. It is meant for link checks and UI acceptance,
    # not final timetable quality comparison.
    "fast": {
        "candidate_pool_size": 250,
        "candidate_top_n": 24,
        "population_size": 30,
        "generations": 25,
        "elite_size": 4,
        "tournament_size": 3,
        "mutation_rate": 0.18,
    },
    "default": {
        "candidate_pool_size": 500,
        "candidate_top_n": 40,
        "population_size": 60,
        "generations": 60,
        "elite_size": 6,
        "tournament_size": 4,
        "mutation_rate": 0.15,
    },
    "quality": {
        "candidate_pool_size": 800,
        "candidate_top_n": 80,
        "population_size": 100,
        "generations": 100,
        "elite_size": 10,
        "tournament_size": 5,
        "mutation_rate": 0.15,
    },
}


def resolve_ga_profile_name(logger=None):
    profile = os.getenv("ML_GA_PROFILE", "default").strip().lower()
    if profile not in GA_PROFILES:
        if logger:
            logger.warning("Unknown ML_GA_PROFILE=%s, falling back to default", profile)
        profile = "default"
    if logger:
        logger.info("ML_GA_PROFILE=%s", profile)
    return profile


def resolve_ga_params(logger=None):
    profile = resolve_ga_profile_name()
    params = {**GA_PROFILES[profile], "profile": profile}
    params["candidate_pool_size"] = _env_int("ML_GA_CANDIDATE_POOL_SIZE", params["candidate_pool_size"], 20, 5000)
    params["candidate_top_n"] = _env_int("ML_GA_CANDIDATE_TOP_N", params["candidate_top_n"], 5, 500)
    params["population_size"] = _env_int("ML_GA_POPULATION_SIZE", params["population_size"], 4, 500)
    params["generations"] = _env_int("ML_GA_GENERATIONS", params["generations"], 1, 500)
    params["elite_size"] = _env_int("ML_GA_ELITE_SIZE", params["elite_size"], 1, params["population_size"])
    params["tournament_size"] = _env_int("ML_GA_TOURNAMENT_SIZE", params["tournament_size"], 2, params["population_size"])
    params["mutation_rate"] = _env_float("ML_GA_MUTATION_RATE", params["mutation_rate"], 0.0, 1.0)
    if logger:
        logger.info("GA params profile=%s pop=%d gen=%d", profile, params["population_size"], params["generations"])
    return params


def collect_ga_env_overrides(logger=None):
    result = {}
    for k in (
        "ML_GA_CANDIDATE_POOL_SIZE",
        "ML_GA_CANDIDATE_TOP_N",
        "ML_GA_POPULATION_SIZE",
        "ML_GA_GENERATIONS",
        "ML_GA_ELITE_SIZE",
        "ML_GA_TOURNAMENT_SIZE",
        "ML_GA_MUTATION_RATE",
    ):
        v = os.getenv(k)
        if v:
            result[k] = v
    if logger and result:
        logger.info("GA env overrides: %s", result)
    return result


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))
