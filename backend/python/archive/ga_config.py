"""GA runtime parameter presets."""

from __future__ import annotations
import os


GA_PROFILES = {
    # Fast keeps validation runs short. It is meant for link checks and UI acceptance,
    # not final timetable quality comparison.
    "fast": {
        "candidate_pool_size": 250,
        "candidate_top_n": 40,
        "population_size": 40,
        "generations": 30,
        "elite_size": 4,
        "tournament_size": 3,
        "mutation_rate": 0.18,
    },
    "default": {
        "candidate_pool_size": 800,
        "candidate_top_n": 80,
        "population_size": 120,
        "generations": 100,
        "elite_size": 10,
        "tournament_size": 4,
        "mutation_rate": 0.12,
    },
    "quality": {
        "candidate_pool_size": 1500,
        "candidate_top_n": 120,
        "population_size": 200,
        "generations": 180,
        "elite_size": 20,
        "tournament_size": 5,
        "mutation_rate": 0.10,
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
    params["candidate_workers"] = _env_int("ML_CANDIDATE_WORKERS", _default_candidate_workers(), 1, 16)
    params["repair_max_tasks"] = _env_int("ML_GA_REPAIR_MAX_TASKS", 2, 0, 16)
    params["repair_candidate_limit"] = _env_int("ML_GA_REPAIR_CANDIDATE_LIMIT", 12, 1, 120)
    params["greedy_init_scan_limit"] = _env_int("ML_GA_GREEDY_INIT_SCAN_LIMIT", 8, 1, 500)
    params["greedy_init_variants"] = _env_int("ML_GA_GREEDY_INIT_VARIANTS", 2, 0, 64)
    params["directed_mutation_scan_limit"] = _env_int("ML_GA_DIRECTED_MUTATION_SCAN_LIMIT", 0, 0, 500)
    params["local_repair_enabled"] = _env_bool("ML_GA_LOCAL_REPAIR_ENABLED", True)
    params["local_repair_candidate_limit"] = _env_int("ML_GA_LOCAL_REPAIR_CANDIDATE_LIMIT", 12, 1, 120)
    params["local_mutation_enabled"] = _env_bool("ML_GA_LOCAL_MUTATION_ENABLED", True)
    params["local_mutation_candidate_limit"] = _env_int("ML_GA_LOCAL_MUTATION_CANDIDATE_LIMIT", 8, 1, 120)
    params["candidate_local_expand_enabled"] = _env_bool("ML_CANDIDATE_LOCAL_EXPAND_ENABLED", True)
    params["candidate_local_expand_slot_limit"] = _env_int("ML_CANDIDATE_LOCAL_EXPAND_SLOT_LIMIT", 12, 1, 120)
    params["candidate_local_expand_room_limit"] = _env_int("ML_CANDIDATE_LOCAL_EXPAND_ROOM_LIMIT", 12, 1, 120)
    params["candidate_local_expand_max_added_per_task"] = _env_int("ML_CANDIDATE_LOCAL_EXPAND_MAX_ADDED_PER_TASK", 80, 0, 1000)
    if logger:
        logger.info(
            "GA params profile=%s pop=%d gen=%d candidate_workers=%d repair_max_tasks=%d repair_candidate_limit=%d "
            "greedy_init_scan_limit=%d greedy_init_variants=%d directed_mutation_scan_limit=%d "
            "local_repair=%s/%d local_mutation=%s/%d candidate_local_expand=%s/%d",
            profile,
            params["population_size"],
            params["generations"],
            params["candidate_workers"],
            params["repair_max_tasks"],
            params["repair_candidate_limit"],
            params["greedy_init_scan_limit"],
            params["greedy_init_variants"],
            params["directed_mutation_scan_limit"],
            params["local_repair_enabled"],
            params["local_repair_candidate_limit"],
            params["local_mutation_enabled"],
            params["local_mutation_candidate_limit"],
            params["candidate_local_expand_enabled"],
            params["candidate_local_expand_max_added_per_task"],
        )
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
        "ML_CANDIDATE_WORKERS",
        "ML_GA_REPAIR_MAX_TASKS",
        "ML_GA_REPAIR_CANDIDATE_LIMIT",
        "ML_GA_GREEDY_INIT_SCAN_LIMIT",
        "ML_GA_GREEDY_INIT_VARIANTS",
        "ML_GA_DIRECTED_MUTATION_SCAN_LIMIT",
        "ML_GA_LOCAL_REPAIR_ENABLED",
        "ML_GA_LOCAL_REPAIR_CANDIDATE_LIMIT",
        "ML_GA_LOCAL_MUTATION_ENABLED",
        "ML_GA_LOCAL_MUTATION_CANDIDATE_LIMIT",
        "ML_CANDIDATE_LOCAL_EXPAND_ENABLED",
        "ML_CANDIDATE_LOCAL_EXPAND_SLOT_LIMIT",
        "ML_CANDIDATE_LOCAL_EXPAND_ROOM_LIMIT",
        "ML_CANDIDATE_LOCAL_EXPAND_MAX_ADDED_PER_TASK",
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _default_candidate_workers() -> int:
    cpu_count = os.cpu_count() or 2
    return max(1, min(cpu_count - 1, 6))
