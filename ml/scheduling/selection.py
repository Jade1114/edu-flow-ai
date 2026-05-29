"""GA selection operators, implementing Deb (2000) feasibility-first principle.

Deb, K. (2000). "An efficient constraint handling method for genetic algorithms."
  Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338.

Selection rules:
  1. Feasible > Infeasible (penalty_count == 0 > penalty_count > 0)
  2. Both feasible → higher quality_score wins
  3. Both infeasible → lower penalty_count wins
"""

from __future__ import annotations
import random
from typing import Any, Callable
from ml.scheduling.types import TaskGene


def deb_tournament_select(
    population: list[list[TaskGene]],
    penalty_fn: Callable[[list[TaskGene]], int],
    quality_fn: Callable[[list[TaskGene]], float],
    k: int = 4,
    rng: random.Random | None = None,
) -> list[TaskGene]:
    """Deb 2000 constrained tournament selection.

    Picks k individuals uniformly from population, returns the best
    by feasibility-first criteria.
    """
    if rng is None:
        rng = random
    candidates = [rng.choice(population) for _ in range(k)]

    # Split by feasibility
    feasible = [c for c in candidates if penalty_fn(c) == 0]

    if feasible:
        # All feasible → pick by quality (higher = better)
        return max(feasible, key=quality_fn)
    else:
        # All infeasible → pick by penalty (lower = better)
        return min(candidates, key=penalty_fn)


def elite_select(
    population: list[list[TaskGene]],
    penalty_fn: Callable[[list[TaskGene]], int],
    quality_fn: Callable[[list[TaskGene]], float],
    elite_size: int,
) -> list[list[TaskGene]]:
    """Select elite individuals for next generation.

    Feasible > Infeasible, then sort by quality/penalty within each group.
    """
    scored = [
        {
            "ind": ind,
            "penalty": penalty_fn(ind),
            "quality": quality_fn(ind),
        }
        for ind in population
    ]

    feasible = [s for s in scored if s["penalty"] == 0]
    infeasible = [s for s in scored if s["penalty"] > 0]

    feasible.sort(key=lambda x: x["quality"], reverse=True)
    infeasible.sort(key=lambda x: x["penalty"])

    ranked = feasible + infeasible
    return [item["ind"][:] for item in ranked[:elite_size]]


def best_individual(
    population: list[list[TaskGene]],
    penalty_fn: Callable[[list[TaskGene]], int],
    quality_fn: Callable[[list[TaskGene]], float],
) -> tuple[list[TaskGene], int, float]:
    """Return best individual by Deb 2000 rules."""
    feasible = [c for c in population if penalty_fn(c) == 0]
    if feasible:
        best = max(feasible, key=quality_fn)
        return best, 0, quality_fn(best)
    best = min(population, key=penalty_fn)
    return best, penalty_fn(best), quality_fn(best)
