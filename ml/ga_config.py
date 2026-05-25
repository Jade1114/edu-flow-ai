"""GA 配置（精简版）"""

from __future__ import annotations
import os, logging


def resolve_ga_profile_name(logger=None):
    profile = os.getenv("ML_GA_PROFILE", "default")
    if logger:
        logger.info("ML_GA_PROFILE=%s", profile)
    return profile


def resolve_ga_params(logger=None):
    env = {
        "candidate_pool_size": int(os.getenv("ML_GA_CANDIDATE_POOL_SIZE", "500")),
        "candidate_top_n": int(os.getenv("ML_GA_CANDIDATE_TOP_N", "60")),
        "population_size": int(os.getenv("ML_GA_POPULATION_SIZE", "100")),
        "generations": int(os.getenv("ML_GA_GENERATIONS", "100")),
        "elite_size": int(os.getenv("ML_GA_ELITE_SIZE", "10")),
        "tournament_size": int(os.getenv("ML_GA_TOURNAMENT_SIZE", "5")),
        "mutation_rate": float(os.getenv("ML_GA_MUTATION_RATE", "0.15")),
    }
    if logger:
        profile = os.getenv("ML_GA_PROFILE", "default")
        logger.info("GA params profile=%s pop=%d gen=%d", profile, env["population_size"], env["generations"])
    return env


def collect_ga_env_overrides(logger=None):
    result = {}
    for k in ("ML_GA_POPULATION_SIZE", "ML_GA_GENERATIONS", "ML_GA_MUTATION_RATE"):
        v = os.getenv(k)
        if v:
            result[k] = v
    if logger and result:
        logger.info("GA env overrides: %s", result)
    return result
