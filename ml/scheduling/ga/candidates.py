"""GA candidate pool building, feature extraction, ranking, and scoring."""

from __future__ import annotations

import random
from collections import Counter
from time import perf_counter
from typing import Any, Optional

import numpy as np

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

from ml import ml_logger
from ml.scheduling.infra.constants import (
    CANDIDATE_DIAGNOSTICS,
    TOTAL_WEEKS,
    WEEKLY_TEMPLATE_SLOTS,
)
from ml.scheduling.domain.features import (
    build_occupied_indexes,
    effective_required_room_type,
    is_room_type_match,
    parse_id_tuple,
    periods_needed,
    reject_reason,
    score_sample,
)
from ml.scheduling.infra.lightgbm import build_features
from ml.scheduling.infra.runtime import RUN_TIMINGS, add_timing, log_chain
from ml.scheduling.domain.teacher_penalties import normalize_unavailable_slots
from ml.scheduling.domain.teacher_profile import parse_optional_int, parse_unavailable_time


def diagnose_candidate_space(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profile: Optional[dict[str, Any]],
    exclude_weekends: bool,
) -> dict[str, Any]:
    required_capacity = int(task.get("total_student_count") or 0)
    required_room_type = effective_required_room_type(task)
    bound_classroom_id = task.get("bound_classroom_id")
    normalized_unavailable = {
        tuple(slot) for slot in normalize_unavailable_slots(
            (teacher_profile or {}).get("unavailable_slots")
        )
    }
    available_time_slots = [
        slot for slot in time_slots
        if not (exclude_weekends and int(slot["day_of_week"]) >= 6)
        and (int(slot["day_of_week"]), int(slot["period_index"])) not in normalized_unavailable
    ]
    capacity_valid_rooms = [
        room for room in classrooms
        if int(room.get("capacity") or 0) >= required_capacity
    ]
    type_valid_rooms = [
        room for room in capacity_valid_rooms
        if is_room_type_match(required_room_type, room.get("classroom_type") or "")
    ]
    final_rooms = type_valid_rooms
    filtered_reasons = {}
    if not available_time_slots:
        filtered_reasons["teacher_or_weekend_time_unavailable"] = len(time_slots)
    if not capacity_valid_rooms:
        filtered_reasons["capacity_not_enough"] = len(classrooms)
    elif not type_valid_rooms:
        filtered_reasons["room_type_mismatch"] = len(capacity_valid_rooms)
    return {
        "task_id": int(task["teaching_task_id"]),
        "teacher_id": int(task["teacher_id"]),
        "teacher_name": task.get("teacher_name") or "",
        "required_fragments": periods_needed(task),
        "required_capacity": required_capacity,
        "required_room_type": required_room_type,
        "bound_classroom_id": bound_classroom_id,
        "available_time_slot_count": len(available_time_slots),
        "available_classrooms": [
            {"id": int(room["id"]), "name": room.get("name") or "",
             "capacity": int(room.get("capacity") or 0),
             "type": room.get("classroom_type") or "",
             "building": room.get("building") or ""}
            for room in sorted(final_rooms, key=lambda r: int(r.get("capacity") or 0), reverse=True)[:20]
        ],
        "max_available_capacity": max([int(r.get("capacity") or 0) for r in final_rooms] or [0]),
        "has_any_available_classroom": bool(final_rooms),
        "has_any_feasible_candidate": bool(final_rooms and available_time_slots),
        "filtered_reason": filtered_reasons or {"ok": 0},
        "suggestions": {
            "allow_split_class": required_capacity > max([int(r.get("capacity") or 0) for r in classrooms] or [0]),
            "allow_room_type_relaxation": bool(required_room_type and capacity_valid_rooms and not type_valid_rooms),
            "allow_capacity_expansion": not bool(capacity_valid_rooms),
            "allow_bound_room_change": bool(bound_classroom_id and type_valid_rooms),
        },
    }


def build_candidate_rows(
    *,
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    selected_assignments: list,
    teacher_profile: Optional[dict[str, Any]] = None,
    exclude_weekends: bool = False,
) -> list[dict[str, Any]]:
    indexes = build_occupied_indexes(selected_assignments)
    scheme_day_load = Counter((a.week_number, a.day_of_week) for a in selected_assignments)
    room_day_load = Counter((a.classroom_id, a.week_number, a.day_of_week) for a in selected_assignments)
    room_week_load = Counter((a.classroom_id, a.week_number) for a in selected_assignments)
    task_day_load = Counter((a.task_id, a.week_number, a.day_of_week) for a in selected_assignments)
    task_id = int(task["teaching_task_id"])
    teacher_id = int(task["teacher_id"])
    class_group_ids = parse_id_tuple(task.get("class_group_ids"))
    required_room_type = effective_required_room_type(task)
    total_student_count = int(task.get("total_student_count") or 0)
    teacher_max_weekly_hours = task.get("teacher_max_weekly_hours")
    required_fragments = periods_needed(task)
    profile = teacher_profile or {}
    profile_preference = (
        profile.get("profile_preference")
        if isinstance(profile.get("profile_preference"), dict)
        else {}
    )
    unavailable_slots = {tuple(s) for s in normalize_unavailable_slots(profile.get("unavailable_slots"))}
    teacher_preferred_weekdays = set(profile_preference.get("preferredWeekdays") or [])
    teacher_avoid_slots = parse_unavailable_time(
        ",".join(str(item) for item in profile_preference.get("avoidSlots") or [])
    )
    preferred_max_weekly_hours = (
        parse_optional_int(profile_preference.get("preferredMaxWeeklyHours"))
        or parse_optional_int(profile.get("max_weekly_hours"))
        or 0
    )
    avoid_first_period = int(bool(profile_preference.get("avoidFirstPeriod")))
    avoid_last_period = int(bool(profile_preference.get("avoidLastPeriod")))
    prefer_compact_schedule = int(bool(profile_preference.get("preferCompactSchedule")))
    filter_started_at = perf_counter()
    filtered_time_slots = [
        slot for slot in time_slots
        if not (exclude_weekends and int(slot["day_of_week"]) >= 6)
        and (int(slot["day_of_week"]), int(slot["period_index"])) not in unavailable_slots
    ]
    filtered_classrooms = [
        room for room in classrooms
        if int(room.get("capacity") or 0) >= total_student_count
        and is_room_type_match(required_room_type, room.get("classroom_type") or "")
    ]
    add_timing("candidate_filter_time", filter_started_at)
    rows: list[dict[str, Any]] = []

    for slot in filtered_time_slots:
        slot_id = int(slot["id"])
        week_number = int(slot["week_number"])
        day_of_week = int(slot["day_of_week"])
        period_index = int(slot["period_index"])
        is_morning = int(period_index in (1, 2))
        is_afternoon = int(period_index in (3, 4))
        is_evening = int(period_index >= 5)
        is_weekend = int(day_of_week >= 6)
        is_early_period = int(period_index == 1)
        is_late_period = int(period_index >= 5)
        teacher_matrix_value = -1 if (day_of_week, period_index) in unavailable_slots else 0
        teacher_preferred_weekday_match = int(day_of_week in teacher_preferred_weekdays) if teacher_preferred_weekdays else 0
        teacher_avoid_slot_match = int((day_of_week, period_index) in teacher_avoid_slots)

        teacher_occupied = bool(indexes["teacher_slot"].get((teacher_id, slot_id)))
        class_occupied = any(
            bool(indexes["class_slot"].get((cg, slot_id))) for cg in class_group_ids
        )
        teacher_day_load = indexes["teacher_day_load"].get((teacher_id, week_number, day_of_week), 0)
        teacher_week_load = indexes["teacher_week_load"].get((teacher_id, week_number), 0)
        class_day_load = max(
            [indexes["class_day_load"].get((cg, week_number, day_of_week), 0) for cg in class_group_ids]
            or [0]
        )
        class_week_load = max(
            [indexes["class_week_load"].get((cg, week_number), 0) for cg in class_group_ids]
            or [0]
        )

        for room in filtered_classrooms:
            room_id = int(room["id"])
            room_capacity = int(room.get("capacity") or 0)
            room_type = room.get("classroom_type") or ""
            room_occupied = bool(indexes["room_slot"].get((room_id, slot_id)))
            capacity_margin = room_capacity - total_student_count
            capacity_ratio = round(total_student_count / room_capacity, 4) if room_capacity > 0 else 1.0
            capacity_enough = room_capacity >= total_student_count if room_capacity > 0 else False
            type_match = is_room_type_match(required_room_type, room_type)
            has_hard_conflict = teacher_occupied or class_occupied or room_occupied or not capacity_enough or not type_match
            rs = score_sample(
                has_hard_conflict=has_hard_conflict, is_type_match=type_match,
                capacity_ratio=capacity_ratio, is_early_period=is_early_period,
                is_late_period=is_late_period, teacher_day_load=teacher_day_load,
                class_day_load=class_day_load, teacher_week_load=teacher_week_load,
                teacher_max_weekly_hours=int(teacher_max_weekly_hours) if teacher_max_weekly_hours is not None else None,
            )
            rows.append({
                "teaching_task_id": task_id, "candidate_classroom_id": room_id,
                "candidate_time_slot_id": slot_id, "course_type": task.get("course_type") or "",
                "total_hours": int(task.get("total_hours") or 0),
                "required_room_type": required_room_type,
                "class_group_count": int(task.get("class_group_count") or 0),
                "total_student_count": total_student_count,
                "teacher_department": task.get("teacher_department") or "",
                "teacher_title": task.get("teacher_title") or "",
                "teacher_max_weekly_hours": teacher_max_weekly_hours or 0,
                "room_capacity": room_capacity, "room_type": room_type,
                "room_building": room.get("building") or "",
                "capacity_margin": capacity_margin, "capacity_ratio": capacity_ratio,
                "week_number": week_number, "day_of_week": day_of_week,
                "period_index": period_index, "is_morning": is_morning,
                "is_afternoon": is_afternoon, "is_evening": is_evening,
                "is_weekend": is_weekend, "is_early_period": is_early_period,
                "is_late_period": is_late_period,
                "required_fragments": required_fragments,
                "teacher_matrix_value": teacher_matrix_value,
                "teacher_preferred_max_weekly_hours": preferred_max_weekly_hours,
                "teacher_avoid_first_period": avoid_first_period,
                "teacher_avoid_last_period": avoid_last_period,
                "teacher_prefer_compact_schedule": prefer_compact_schedule,
                "teacher_preferred_weekday_match": teacher_preferred_weekday_match,
                "teacher_avoid_slot_match": teacher_avoid_slot_match,
                "teacher_occupied_at_slot": int(teacher_occupied),
                "class_occupied_at_slot": int(class_occupied),
                "room_occupied_at_slot": int(room_occupied),
                "teacher_day_load": teacher_day_load, "class_day_load": class_day_load,
                "teacher_week_load": teacher_week_load, "class_week_load": class_week_load,
                "scheme_day_load": scheme_day_load.get((week_number, day_of_week), 0),
                "room_day_load": room_day_load.get((room_id, week_number, day_of_week), 0),
                "room_week_load": room_week_load.get((room_id, week_number), 0),
                "task_day_load": task_day_load.get((task_id, week_number, day_of_week), 0),
                "is_capacity_enough": int(capacity_enough),
                "is_room_type_match": int(type_match),
                "has_teacher_conflict": int(teacher_occupied),
                "has_class_conflict": int(class_occupied),
                "has_room_conflict": int(room_occupied),
                "has_hard_conflict": int(has_hard_conflict),
                "rule_score": rs,
                "reject_reason": reject_reason(
                    teacher_conflict=teacher_occupied, class_conflict=class_occupied,
                    room_conflict=room_occupied, capacity_enough=capacity_enough,
                    type_match=type_match,
                ),
            })
    return rows


def shortlist_candidates(candidates: list[dict[str, Any]], pool_size: int, rng: random.Random) -> list[dict[str, Any]]:
    if pool_size <= 0 or len(candidates) <= pool_size:
        return candidates
    legal = [c for c in candidates if int(c["has_hard_conflict"]) == 0]
    pool = legal if legal else candidates
    return sorted(
        pool,
        key=lambda r: (
            -int(r["has_hard_conflict"]), r["rule_score"],
            -r["scheme_day_load"], -r["room_day_load"],
            -r["room_week_load"], -r["task_day_load"], rng.random(),
        ),
        reverse=True,
    )[:pool_size]


def apply_selection_scores(
    candidates: list[dict[str, Any]],
    rng: random.Random,
    rule_weights: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> None:
    for candidate in candidates:
        dist_penalty = (
            candidate["scheme_day_load"] * rule_weights["weekday_load_penalty"]
            + candidate["room_day_load"] * rule_weights["room_day_load_penalty"]
            + candidate["room_week_load"] * rule_weights["room_week_load_penalty"]
            + candidate["task_day_load"] * rule_weights["task_day_load_penalty"]
        )
        weekend_penalty = int(candidate.get("is_weekend", 0)) * rule_weights.get("weekend_penalty", 0.0)
        early_penalty = int(candidate.get("is_early_period", 0)) * rule_weights["early_period_penalty"]
        late_penalty = int(candidate.get("is_late_period", 0)) * rule_weights["late_period_penalty"]
        compact_bonus = candidate.get("scheme_day_load", 0) * rule_weights["compact_bonus_weight"]

        stickiness_bonus = 0.0
        if task_classroom_id is not None:
            candidate_room = int(candidate.get("candidate_classroom_id", 0))
            if candidate_room == task_classroom_id:
                stickiness_bonus = float(rule_weights.get("classroom_stickiness_bonus", 0.0))

        teacher_profile_penalty = 0.0
        teacher_profile_penalty_breakdown: list[dict[str, Any]] = []
        if teacher_id is not None and teacher_profiles is not None:
            profile = teacher_profiles.get(teacher_id)
            if profile is not None:
                unavailable = profile.get("unavailable_slots", [])
                day = int(candidate.get("day_of_week", 0))
                period = int(candidate.get("period_index", 0))
                n_slots = {tuple(s) for s in normalize_unavailable_slots(unavailable)}
                if (day, period) in n_slots:
                    p = float(profile.get("penalty_weight") or 0.05)
                    teacher_profile_penalty += p
                    teacher_profile_penalty_breakdown.append({
                        "type": "unavailable_slot", "penalty": round(p, 4),
                        "day_of_week": day, "period_index": period,
                        "reason": profile.get("reason") or "teacher unavailable slot",
                    })
                pref_max = profile.get("max_weekly_hours")
                if pref_max is not None:
                    cur_hours = int(candidate.get("teacher_week_load", 0))
                    if cur_hours + 1 > int(pref_max):
                        p = 0.03
                        teacher_profile_penalty += p
                        teacher_profile_penalty_breakdown.append({
                            "type": "max_weekly_hours_exceeded", "penalty": round(p, 4),
                            "teacher_week_load_before": cur_hours,
                            "max_weekly_hours": int(pref_max),
                            "reason": profile.get("reason") or "teacher preferred max weekly hours exceeded",
                        })

        random_jitter = rng.random() * rule_weights["random_jitter"]
        candidate["distribution_penalty"] = round(dist_penalty + weekend_penalty + early_penalty + late_penalty, 6)
        candidate["compact_bonus"] = round(compact_bonus, 6)
        candidate["stickiness_bonus"] = round(stickiness_bonus, 6)
        candidate["teacher_profile_penalty"] = round(teacher_profile_penalty, 4)
        candidate["teacher_profile_penalty_breakdown"] = teacher_profile_penalty_breakdown
        candidate["random_jitter_value"] = round(random_jitter, 6)
        candidate["selection_score"] = max(
            0.0,
            float(candidate["predicted_score"])
            + float(candidate["rule_score"]) * 0.02
            - candidate["distribution_penalty"]
            + compact_bonus + stickiness_bonus + random_jitter,
        )


def rank_candidates(
    *,
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    candidates: list[dict[str, Any]],
    rng: random.Random,
    rule_weights: dict[str, float],
    task_classroom_id: int | None = None,
    teacher_id: int | None = None,
    teacher_profiles: dict[int, dict[str, object]] | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    model_used = booster is not None and schema is not None
    if model_used:
        features = build_features(candidates, schema)
        predictions = np.clip(booster.predict(features), 0.0, 1.0)
        for cand, ps in zip(candidates, predictions):
            cand["predicted_score"] = float(ps)
        scores = [c["predicted_score"] for c in candidates]
        ml_logger.scoring_batch(
            task_id=int(candidates[0].get("teaching_task_id", 0)),
            candidate_count=len(candidates),
            score_mean=float(np.mean(scores)), score_std=float(np.std(scores)),
            score_min=float(np.min(scores)), score_max=float(np.max(scores)),
            model_used=True,
        )
    else:
        for cand in candidates:
            cand["predicted_score"] = float(cand.get("rule_score") or 0.0)
        scores = [c["predicted_score"] for c in candidates]
        ml_logger.scoring_batch(
            task_id=int(candidates[0].get("teaching_task_id", 0)),
            candidate_count=len(candidates),
            score_mean=float(np.mean(scores)) if scores else 0.0,
            score_std=0.0, score_min=float(np.min(scores)) if scores else 0.0,
            score_max=float(np.max(scores)) if scores else 0.0,
            model_used=False,
        )
    apply_selection_scores(candidates, rng, rule_weights, task_classroom_id, teacher_id, teacher_profiles)
    return sorted(
        candidates, key=lambda r: (r["selection_score"], -r["has_hard_conflict"],
                                   r["predicted_score"], r["rule_score"]),
        reverse=True,
    )


def summarize_candidate_pool(
    raw_candidates: list[dict[str, Any]], pool_candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    raw_hard = sum(int(c.get("has_hard_conflict") or 0) for c in raw_candidates)
    sel_hard = sum(int(c.get("has_hard_conflict") or 0) for c in pool_candidates)
    raw_reasons = Counter(
        str(c.get("reject_reason") or "ok") for c in raw_candidates if int(c.get("has_hard_conflict") or 0) == 1
    )
    sel_reasons = Counter(
        str(c.get("reject_reason") or "ok") for c in pool_candidates if int(c.get("has_hard_conflict") or 0) == 1
    )
    return {
        "raw_candidate_count": len(raw_candidates),
        "raw_legal_candidate_count": len(raw_candidates) - raw_hard,
        "raw_hard_candidate_count": raw_hard,
        "selected_candidate_count": len(pool_candidates),
        "selected_legal_candidate_count": len(pool_candidates) - sel_hard,
        "selected_hard_candidate_count": sel_hard,
        "raw_reject_reason_top": dict(raw_reasons.most_common(5)),
        "selected_reject_reason_top": dict(sel_reasons.most_common(5)),
    }


def log_selected_candidate(task: dict[str, Any], fragment_index: int, best: dict[str, Any], candidate_count: int) -> None:
    candidate_stats = best.get("teacher_profile_candidate_stats") or {}
    if int(candidate_stats.get("penalized_candidate_count") or 0) > 0:
        log_chain("教师画像候选惩罚统计", {
            "teaching_task_id": task.get("teaching_task_id"),
            "teacher_id": task.get("teacher_id"),
            "teacher_name": task.get("teacher_name") or "",
            "fragment_index": fragment_index,
            "selected_penalty": best.get("teacher_profile_penalty"),
            "selected_penalty_breakdown": best.get("teacher_profile_penalty_breakdown") or [],
            **candidate_stats,
        })
    penalty_breakdown = best.get("teacher_profile_penalty_breakdown") or []
    if penalty_breakdown:
        log_chain("教师画像惩罚命中", {
            "teaching_task_id": task.get("teaching_task_id"),
            "teacher_id": task.get("teacher_id"),
            "teacher_name": task.get("teacher_name") or "",
            "fragment_index": fragment_index,
            "chosen_time": {"time_slot_id": best.get("candidate_time_slot_id"),
                            "week_number": best.get("week_number"),
                            "day_of_week": best.get("day_of_week"),
                            "period_index": best.get("period_index")},
            "total_penalty": best.get("teacher_profile_penalty"),
            "breakdown": penalty_breakdown,
        })
    log_chain("模型选择排课片段", {
        "teaching_task_id": task.get("teaching_task_id"),
        "teacher_id": task.get("teacher_id"),
        "teacher_name": task.get("teacher_name") or "",
        "fragment_index": fragment_index,
        "candidate_count": candidate_count,
    })


def build_candidate_pools(
    *,
    tasks: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict[int, dict[str, object]],
    booster: Optional[lgb.Booster],
    schema: Optional[dict[str, Any]],
    max_tasks: int | None,
    rng: random.Random,
    candidate_pool_size: int,
    candidate_top_n: int,
    rule_weights: dict[str, float],
    exclude_weekends: bool,
) -> list[dict[str, Any]]:
    pools: list[dict[str, Any]] = []
    scoped_tasks = tasks[:max_tasks] if max_tasks is not None else tasks
    started_at = perf_counter()
    total_raw = 0
    total_legal = 0
    for task in scoped_tasks:
        task_started_at = perf_counter()
        task_id = int(task["teaching_task_id"])
        teacher_id = int(task["teacher_id"])
        required_fragments = periods_needed(task)
        teacher_profile = teacher_profiles.get(teacher_id)
        diagnostic = diagnose_candidate_space(task, classrooms, time_slots, teacher_profile, exclude_weekends)
        if not diagnostic["has_any_feasible_candidate"]:
            diagnostic["missing_fragment_count"] = required_fragments
            diagnostic["raw_candidate_count"] = 0
            diagnostic["legal_candidate_count"] = 0
            diagnostic["selected_candidate_count"] = 0
            CANDIDATE_DIAGNOSTICS[task_id] = diagnostic
            continue
        candidates = build_candidate_rows(
            task=task, classrooms=classrooms, time_slots=time_slots,
            selected_assignments=[], teacher_profile=teacher_profile,
            exclude_weekends=exclude_weekends,
        )
        legal = [c for c in candidates if int(c.get("has_hard_conflict") or 0) == 0]
        total_raw += len(candidates)
        total_legal += len(legal)
        ranked = rank_candidates(
            booster=booster, schema=schema,
            candidates=shortlist_candidates(legal, candidate_pool_size, rng),
            rng=rng, rule_weights=rule_weights,
            task_classroom_id=task.get("bound_classroom_id"),
            teacher_id=teacher_id, teacher_profiles=teacher_profiles,
        )
        pool_candidates = ranked[: max(1, min(candidate_top_n, len(ranked)))]
        base_summary = summarize_candidate_pool(candidates, pool_candidates)
        base_weekly = min(WEEKLY_TEMPLATE_SLOTS, required_fragments)
        covered_weeks = required_fragments // base_weekly if base_weekly > 0 else 0
        extra_fragments = required_fragments - base_weekly * covered_weeks

        if base_weekly > 0 and pool_candidates:
            seen_key: set[tuple[int, int, int]] = set()
            template_pool: list[dict[str, Any]] = []
            for c in pool_candidates:
                k = (int(c["day_of_week"]), int(c["period_index"]), int(c["candidate_classroom_id"]))
                if k not in seen_key:
                    seen_key.add(k)
                    template_pool.append(c)
            tpl_top_n = min(30, len(template_pool))
            for tpl_idx in range(base_weekly):
                pools.append({
                    "task": task, "task_id": task_id, "teacher_id": teacher_id,
                    "class_group_ids": parse_id_tuple(task.get("class_group_ids")),
                    "fragment_index": tpl_idx + 1,
                    "is_template": True, "covered_weeks": covered_weeks,
                    "candidates": template_pool[:tpl_top_n],
                })
            for ext_idx in range(extra_fragments):
                pools.append({
                    "task": task, "task_id": task_id, "teacher_id": teacher_id,
                    "class_group_ids": parse_id_tuple(task.get("class_group_ids")),
                    "fragment_index": base_weekly + ext_idx + 1,
                    "is_template": False, "candidates": pool_candidates,
                })
        else:
            for fi in range(1, required_fragments + 1):
                pools.append({
                    "task": task, "task_id": task_id, "teacher_id": teacher_id,
                    "class_group_ids": parse_id_tuple(task.get("class_group_ids")),
                    "fragment_index": fi, "is_template": False,
                    "candidates": pool_candidates,
                })
        diagnostic.update({
            "raw_candidate_count": len(candidates),
            "legal_candidate_count": len(legal),
            "selected_candidate_count": len(pool_candidates),
            "missing_fragment_count": 0 if pool_candidates else required_fragments,
            "candidate_summary": base_summary,
        })
        CANDIDATE_DIAGNOSTICS[task_id] = diagnostic
        if not pool_candidates:
            log_chain("GA 硬合法候选池为空", {
                "teaching_task_id": task_id, "teacher_id": teacher_id,
                "fragment_count": required_fragments,
                "has_any_feasible_candidate": diagnostic.get("has_any_feasible_candidate"),
                "suggestions": diagnostic.get("suggestions"),
            })
        log_chain("GA 候选池任务诊断", {
            "teaching_task_id": task_id, "teacher_id": teacher_id,
            "required_fragments": required_fragments,
            "build_duration_ms": round((perf_counter() - task_started_at) * 1000, 2),
        })
    log_chain("GA 候选池全局诊断", {
        "pool_count": len(pools), "tasks": len(scoped_tasks),
        "raw_candidate_count": total_raw, "legal_candidate_count": total_legal,
        "candidate_top_n": candidate_top_n, "candidate_pool_size": candidate_pool_size,
        "build_duration_ms": round((perf_counter() - started_at) * 1000, 2),
    })
    return pools
