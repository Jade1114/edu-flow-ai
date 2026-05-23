"""Pure GA selection/crossover/mutation operators."""

from __future__ import annotations

import random
from typing import Any


def tournament_select(scored: list[dict[str, Any]], tournament_size: int, rng: random.Random) -> list[int]:
    contenders = rng.sample(scored, k=min(tournament_size, len(scored)))
    return max(contenders, key=lambda item: item["metrics"]["fitness"])["individual"][:]


def crossover(parent_a: list[int], parent_b: list[int], pools: list[dict[str, Any]], rng: random.Random) -> list[int]:
    task_ids = sorted({pool["task_id"] for pool in pools})
    inherited_from_a = set(rng.sample(task_ids, k=max(1, len(task_ids) // 2))) if task_ids else set()
    return [
        parent_a[index] if pools[index]["task_id"] in inherited_from_a else parent_b[index]
        for index in range(len(pools))
    ]


def mutate(individual: list[int], pools: list[dict[str, Any]], mutation_rate: float, rng: random.Random) -> None:
    for index, pool in enumerate(pools):
        if rng.random() < mutation_rate and len(pool["candidates"]) > 1:
            individual[index] = rng.randrange(len(pool["candidates"]))
