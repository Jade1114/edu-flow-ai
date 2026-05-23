"""GA individual fitness evaluation and repair helpers."""

from __future__ import annotations

import json
import random
from collections import Counter
from typing import Any

from ml.scheduling.infra.constants import TOTAL_WEEKS
from ml.scheduling.domain.features import PseudoAssignment
from ml.scheduling.infra.runtime import add_timing, log_chain
from ml.scheduling.domain.teacher_penalties import format_teacher_profile_penalty_explanation


def _template_ts_ids(day: int, period: int, weeks: int = TOTAL_WEEKS) -> list[int]:
    return [_w * 10_000 + day * 100 + period for _w in range(1, weeks + 1)]


def _real_time_slot_id(week: int, day: int, period: int) -> int:
    return (week - 1) * 35 + (day - 1) * 5 + period


def conflicts_with_occupied(candidate: dict[str, Any], pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]]) -> bool:
    classroom_id = int(candidate["candidate_classroom_id"])
    if int(candidate.get("has_hard_conflict") or 0) == 1:
        return True
    if pool.get("is_template"):
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        cw = pool.get("covered_weeks", TOTAL_WEEKS)
        for ts_id in _template_ts_ids(day, period, cw):
            if (pool["teacher_id"], ts_id) in occupied["teacher_slot"]:
                return True
            if (classroom_id, ts_id) in occupied["room_slot"]:
                return True
            if any((cg, ts_id) in occupied["class_slot"] for cg in pool["class_group_ids"]):
                return True
        return False
    else:
        time_slot_id = int(candidate["candidate_time_slot_id"])
        if (pool["teacher_id"], time_slot_id) in occupied["teacher_slot"]:
            return True
        if (classroom_id, time_slot_id) in occupied["room_slot"]:
            return True
        return any((cg, time_slot_id) in occupied["class_slot"] for cg in pool["class_group_ids"])


def occupy_candidate(candidate: dict[str, Any], pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]]) -> None:
    classroom_id = int(candidate["candidate_classroom_id"])
    if pool.get("is_template"):
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        cw = pool.get("covered_weeks", TOTAL_WEEKS)
        for ts_id in _template_ts_ids(day, period, cw):
            occupied["teacher_slot"].add((pool["teacher_id"], ts_id))
            occupied["room_slot"].add((classroom_id, ts_id))
            for cg in pool["class_group_ids"]:
                occupied["class_slot"].add((cg, ts_id))
    else:
        time_slot_id = int(candidate["candidate_time_slot_id"])
        occupied["teacher_slot"].add((pool["teacher_id"], time_slot_id))
        occupied["room_slot"].add((classroom_id, time_slot_id))
        for cg in pool["class_group_ids"]:
            occupied["class_slot"].add((cg, time_slot_id))


def empty_occupied() -> dict[str, set[tuple[int, int]]]:
    return {"teacher_slot": set(), "room_slot": set(), "class_slot": set()}


def choose_feasible_gene(pool: dict[str, Any], occupied: dict[str, set[tuple[int, int]]], rng: random.Random) -> int | None:
    feasible_indexes = [
        idx for idx, candidate in enumerate(pool["candidates"])
        if not conflicts_with_occupied(candidate, pool, occupied)
    ]
    if not feasible_indexes:
        return None
    preferred = feasible_indexes[: min(10, len(feasible_indexes))]
    return rng.choice(preferred)


def repair_individual(individual: list[int], pools: list[dict[str, Any]], rng: random.Random, log_unresolved: bool = False) -> list[int]:
    repaired = individual[:]
    occupied = empty_occupied()
    order = list(range(len(pools)))
    order.sort(key=lambda i: (len(pools[i]["candidates"]), rng.random()))
    unresolved: list[int] = []
    for idx in order:
        pool = pools[idx]
        current_gene = repaired[idx]
        current_candidate = pool["candidates"][current_gene]
        if not conflicts_with_occupied(current_candidate, pool, occupied):
            occupy_candidate(current_candidate, pool, occupied)
            continue
        replacement = choose_feasible_gene(pool, occupied, rng)
        if replacement is None:
            unresolved.append(idx)
            continue
        repaired[idx] = replacement
        occupy_candidate(pool["candidates"][replacement], pool, occupied)
    if unresolved and log_unresolved:
        log_chain("GA repair 未能完全消除冲突", {"unresolved_fragment_count": len(unresolved), "sample_indexes": unresolved[:10]})
    return repaired


def random_individual(pools: list[dict[str, Any]], rng: random.Random) -> list[int]:
    raw = [rng.randrange(len(pool["candidates"])) for pool in pools]
    return repair_individual(raw, pools, rng)


def expand_template_individual(individual: list[int], pools: list[dict[str, Any]]) -> list[tuple[int, int, int, int, int]]:
    expanded: list[tuple[int, int, int, int, int]] = []
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        classroom = int(candidate["candidate_classroom_id"])
        if pool.get("is_template"):
            for week in range(1, pool.get("covered_weeks", TOTAL_WEEKS) + 1):
                expanded.append((week, day, period, classroom, pool["task_id"]))
        else:
            week = int(candidate["week_number"])
            expanded.append((week, day, period, classroom, pool["task_id"]))
    return expanded


def individual_rows(individual: list[int], pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seq = 0
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        task = pool["task"]
        penalty_breakdown = candidate.get("teacher_profile_penalty_breakdown") or []
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        classroom = int(candidate["candidate_classroom_id"])
        candidate_ts_id = int(candidate["candidate_time_slot_id"])
        if pool.get("is_template"):
            for week in range(1, pool.get("covered_weeks", TOTAL_WEEKS) + 1):
                seq += 1
                rows.append({
                    "sequence": seq,
                    "teaching_task_id": pool["task_id"],
                    "teacher_id": pool["teacher_id"],
                    "teacher_name": task.get("teacher_name") or "",
                    "fragment_index": pool["fragment_index"],
                    "classroom_id": classroom,
                    "time_slot_id": _real_time_slot_id(week, day, period),
                    "week_number": week,
                    "day_of_week": day,
                    "period_index": period,
                    "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 4),
                    "rule_score": candidate.get("rule_score") or 0.0,
                    "has_hard_conflict": candidate.get("has_hard_conflict") or 0,
                    "reject_reason": candidate.get("reject_reason") or "",
                    "teacher_profile_penalty": candidate.get("teacher_profile_penalty") or 0.0,
                    "teacher_profile_penalty_explanation": format_teacher_profile_penalty_explanation(candidate),
                    "teacher_profile_penalty_breakdown": json.dumps(penalty_breakdown, ensure_ascii=False),
                })
        else:
            seq += 1
            rows.append({
                "sequence": seq,
                "teaching_task_id": pool["task_id"],
                "teacher_id": pool["teacher_id"],
                "teacher_name": task.get("teacher_name") or "",
                "fragment_index": pool["fragment_index"],
                "classroom_id": classroom,
                "time_slot_id": candidate_ts_id,
                "week_number": int(candidate["week_number"]),
                "day_of_week": day,
                "period_index": period,
                "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 4),
                "rule_score": candidate.get("rule_score") or 0.0,
                "has_hard_conflict": candidate.get("has_hard_conflict") or 0,
                "reject_reason": candidate.get("reject_reason") or "",
                "teacher_profile_penalty": candidate.get("teacher_profile_penalty") or 0.0,
                "teacher_profile_penalty_explanation": format_teacher_profile_penalty_explanation(candidate),
                "teacher_profile_penalty_breakdown": json.dumps(penalty_breakdown, ensure_ascii=False),
            })
    return rows


def individual_assignments(individual: list[int], pools: list[dict[str, Any]]) -> list[PseudoAssignment]:
    assignments: list[PseudoAssignment] = []
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        classroom = int(candidate["candidate_classroom_id"])
        ts_id = int(candidate["candidate_time_slot_id"])
        task_id = pool["task_id"]
        if pool.get("is_template"):
            for week in range(1, pool.get("covered_weeks", TOTAL_WEEKS) + 1):
                assignments.append(PseudoAssignment(
                    task_id=task_id, teacher_id=pool["teacher_id"],
                    class_group_ids=pool["class_group_ids"], classroom_id=classroom,
                    time_slot_id=_real_time_slot_id(week, day, period),
                    week_number=week, day_of_week=day, period_index=period,
                ))
        else:
            assignments.append(PseudoAssignment(
                task_id=task_id, teacher_id=pool["teacher_id"],
                class_group_ids=pool["class_group_ids"], classroom_id=classroom,
                time_slot_id=ts_id, week_number=int(candidate["week_number"]),
                day_of_week=day, period_index=period,
            ))
    return assignments


def summarize_individual_conflict_hotspots(individual: list[int], pools: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    teacher_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    room_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    class_slot: dict[tuple[int, int], list[dict[str, Any]]] = {}
    candidate_conflicts: list[dict[str, Any]] = []
    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        day = int(candidate["day_of_week"])
        period = int(candidate["period_index"])
        classroom = int(candidate["candidate_classroom_id"])
        ts_id = int(candidate["candidate_time_slot_id"])
        week = int(candidate["week_number"])
        if pool.get("is_template"):
            cw = pool.get("covered_weeks", TOTAL_WEEKS)
            items: list[dict[str, Any]] = [
                {"task_id": pool["task_id"], "teacher_id": pool["teacher_id"],
                 "fragment_index": pool["fragment_index"], "classroom_id": classroom,
                 "time_slot_id": _w * 10_000 + day * 100 + period,
                 "week_number": _w, "day_of_week": day, "period_index": period,
                 "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 6),
                 "rule_score": round(float(candidate.get("rule_score") or 0.0), 6),
                 "reject_reason": candidate.get("reject_reason") or ""}
                for _w in range(1, cw + 1)
            ]
            for item in items:
                teacher_slot.setdefault((pool["teacher_id"], item["time_slot_id"]), []).append(item)
                room_slot.setdefault((item["classroom_id"], item["time_slot_id"]), []).append(item)
                for cg in pool["class_group_ids"]:
                    class_slot.setdefault((cg, item["time_slot_id"]), []).append(item)
            if int(candidate.get("has_hard_conflict") or 0) == 1:
                candidate_conflicts.extend(items)
        else:
            item = {
                "task_id": pool["task_id"], "teacher_id": pool["teacher_id"],
                "fragment_index": pool["fragment_index"], "classroom_id": classroom,
                "time_slot_id": ts_id, "week_number": week,
                "day_of_week": day, "period_index": period,
                "predicted_score": round(float(candidate.get("predicted_score") or 0.0), 6),
                "rule_score": round(float(candidate.get("rule_score") or 0.0), 6),
                "reject_reason": candidate.get("reject_reason") or "",
            }
            teacher_slot.setdefault((pool["teacher_id"], item["time_slot_id"]), []).append(item)
            room_slot.setdefault((item["classroom_id"], item["time_slot_id"]), []).append(item)
            for cg in pool["class_group_ids"]:
                class_slot.setdefault((cg, item["time_slot_id"]), []).append(item)
            if int(candidate.get("has_hard_conflict") or 0) == 1:
                candidate_conflicts.append(item)

    def top_duplicates(idx: dict) -> list:
        dupes = [
            {"key": key, "count": len(items), "items": items[:5]}
            for key, items in idx.items() if len(items) > 1
        ]
        dupes.sort(key=lambda r: r["count"], reverse=True)
        return dupes[:limit]

    return {
        "candidate_conflicts_sample": candidate_conflicts[:limit],
        "teacher_slot_duplicates": top_duplicates(teacher_slot),
        "room_slot_duplicates": top_duplicates(room_slot),
        "class_slot_duplicates": top_duplicates(class_slot),
    }


def evaluate_individual(
    individual: list[int],
    pools: list[dict[str, Any]],
    *,
    predicted_score_weight: float,
    rule_score_weight: float,
    hard_conflict_penalty: float,
    distribution_penalty_scale: float,
    classroom_stickiness_weight: float,
    compact_bonus_weight: float,
) -> dict[str, Any]:
    if not individual:
        return {"fitness": -1_000_000.0}
    teacher_slot: Counter[tuple[int, int]] = Counter()
    class_slot: Counter[tuple[int, int]] = Counter()
    room_slot: Counter[tuple[int, int]] = Counter()
    day_load: Counter[tuple[int, int]] = Counter()
    task_day_load: Counter[tuple[int, int, int]] = Counter()
    task_rooms: dict[int, set[int]] = {}
    predicted_total = 0.0
    rule_total = 0.0
    candidate_hard_conflicts = 0
    teacher_profile_penalty_total = 0.0

    for gene, pool in zip(individual, pools):
        candidate = pool["candidates"][gene]
        teacher_id = pool["teacher_id"]
        room_id = int(candidate["candidate_classroom_id"])
        day_of_week = int(candidate["day_of_week"])
        period_index = int(candidate["period_index"])
        predicted_total += float(candidate.get("predicted_score") or 0.0)
        rule_total += float(candidate.get("rule_score") or 0.0)
        candidate_hard_conflicts += int(candidate.get("has_hard_conflict") or 0)
        teacher_profile_penalty_total += float(candidate.get("teacher_profile_penalty") or 0.0)
        if pool.get("is_template"):
            for _w in range(1, pool.get("covered_weeks", TOTAL_WEEKS) + 1):
                _ts_id = _w * 10_000 + day_of_week * 100 + period_index
                teacher_slot[(teacher_id, _ts_id)] += 1
                room_slot[(room_id, _ts_id)] += 1
                for cg in pool["class_group_ids"]:
                    class_slot[(cg, _ts_id)] += 1
                day_load[(_w, day_of_week)] += 1
                task_day_load[(pool["task_id"], _w, day_of_week)] += 1
        else:
            time_slot_id = int(candidate["candidate_time_slot_id"])
            week_number = int(candidate["week_number"])
            teacher_slot[(teacher_id, time_slot_id)] += 1
            room_slot[(room_id, time_slot_id)] += 1
            for cg in pool["class_group_ids"]:
                class_slot[(cg, time_slot_id)] += 1
            day_load[(week_number, day_of_week)] += 1
            task_day_load[(pool["task_id"], week_number, day_of_week)] += 1
        task_rooms.setdefault(pool["task_id"], set()).add(room_id)

    teacher_slot_conflicts = sum(c - 1 for c in teacher_slot.values() if c > 1)
    room_slot_conflicts = sum(c - 1 for c in room_slot.values() if c > 1)
    class_slot_conflicts = sum(c - 1 for c in class_slot.values() if c > 1)
    duplicate_conflicts = teacher_slot_conflicts + room_slot_conflicts + class_slot_conflicts
    hard_conflicts = candidate_hard_conflicts + duplicate_conflicts
    distribution_penalty = sum(max(0, c - 4) for c in day_load.values())
    distribution_penalty += sum(max(0, c - 2) for c in task_day_load.values())
    classroom_switches = sum(max(0, len(rids) - 1) for rids in task_rooms.values())
    compact_bonus = sum(max(0, c - 1) for c in task_day_load.values())

    size = len(individual)
    avg_predicted = predicted_total / size
    avg_rule = rule_total / size
    soft_score = (
        avg_predicted * predicted_score_weight
        + avg_rule * rule_score_weight
        - distribution_penalty * distribution_penalty_scale
        - classroom_switches * classroom_stickiness_weight
        + compact_bonus * compact_bonus_weight
    )
    fitness = -hard_conflicts * hard_conflict_penalty + soft_score
    return {
        "fitness": round(fitness, 6),
        "soft_score": round(soft_score, 6),
        "avg_predicted_score": round(avg_predicted, 6),
        "avg_rule_score": round(avg_rule, 6),
        "hard_conflict_count": hard_conflicts,
        "candidate_hard_conflict_count": candidate_hard_conflicts,
        "duplicate_conflict_count": duplicate_conflicts,
        "teacher_slot_conflict_count": teacher_slot_conflicts,
        "room_slot_conflict_count": room_slot_conflicts,
        "class_slot_conflict_count": class_slot_conflicts,
        "teacher_profile_penalty_total": round(teacher_profile_penalty_total, 6),
        "distribution_penalty": distribution_penalty,
        "classroom_switches": classroom_switches,
        "compact_bonus": compact_bonus,
    }
