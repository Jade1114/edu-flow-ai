"""Quality scoring pipeline: L2 soft constraints + L3 model + L5 LLM.

Independent from ga.py's fitness function. Returns a [0, 1] value
representing schedule quality — higher is better.

Layers:
  L2 — rule-based soft constraints (weights from generation_config)
  L3 — LightGBM model score (alpha weight)
  L5 — LLM temporary override (beta weight)
"""

from __future__ import annotations
import logging
from typing import Any
from ml.scheduling.types import (
    AllocationTask, TaskGene, TemplateAssignment,
    slot_to_day_period,
)

_log = logging.getLogger("ga")

# ── Default config (overridden by generation_config at runtime) ────

DEFAULT_CONFIG: dict[str, Any] = {
    "same_day_weight": 0.05,
    "late_period_penalty": 0.05,
    "early_period_penalty": 0.08,
    "profile_penalty_scale": 0.001,
    "capacity_waste_penalty": 0.10,
    "teacher_day_load_penalty": 0.03,
    "class_day_load_penalty": 0.02,
    "teacher_overload_penalty": 0.10,
    "model_weight": 0.6,
    "llm_weight": 0.4,
}


def quality_score(
    chromosome: list[TaskGene],
    tasks: list[AllocationTask],
    scorer=None,
    llm_overrides: list[dict] | None = None,
    config: dict[str, Any] | None = None,
) -> float:
    """Evaluate chromosome quality as [0, 1].

    Combines:
      L2 — rule-based soft constraints (same-day, late, early, profile, load)
      L3 — LightGBM per-assignment scores → weighted by model_weight (α)
      L5 — LLM override evaluations → weighted by llm_weight (β)

    Returns: 1.0 = perfect, 0.0 = unusable.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    task_map = {t.task_id: t for t in tasks}
    ts_map = {t.task_id: t.template_sets for t in tasks}

    # ── Expand chromosome & collect stats ──
    total_assignments = 0
    ml_score_sum = 0.0
    llm_score_sum = 0.0
    same_day_penalty = 0.0
    late_penalty = 0.0
    early_penalty = 0.0
    profile_penalty_sum = 0.0

    for gene in chromosome:
        task = task_map.get(gene.task_id)
        if not task:
            continue
        tss = ts_map.get(gene.task_id, [])
        ts = tss[gene.template_set_id] if gene.template_set_id < len(tss) else None
        if not ts:
            continue

        same_day_slots: set[int] = set()
        for a in gene.assignments:
            tmpl = ts.templates[a.template_id] if a.template_id < len(ts.templates) else None
            if not tmpl:
                continue
            total_assignments += 1

            day, period = slot_to_day_period(a.slot_id)
            same_day_slots.add(day)

            # L2: time preference
            if period == 1:
                early_penalty += cfg["early_period_penalty"]
            if period >= 4:
                late_penalty += cfg["late_period_penalty"]

            # L2: teacher profile soft penalty
            pv, _ = _profile_penalty(task.teacher_profile, a.slot_id)
            profile_penalty_sum += pv * len(tmpl.weeks_list) * cfg["profile_penalty_scale"]

            # L3: model score
            if scorer:
                ml_score_sum += scorer.score(task, tmpl, a.slot_id, a.classroom_id)

            # L5: LLM override evaluation
            if llm_overrides:
                llm_score_sum += _llm_evaluate(a, task, gene, llm_overrides, cfg)

        # L2: same-day penalty
        if len(same_day_slots) > 1 and len(gene.assignments) > 1:
            same_day_penalty += cfg["same_day_weight"] * (len(gene.assignments) - 1)

    if total_assignments == 0:
        return 0.0

    # ── Normalize ──
    l2_penalty = (
        same_day_penalty
        + late_penalty
        + early_penalty
        + profile_penalty_sum
    )
    # cap L2 penalty to [0, 0.5] so model/LLM can still dominate when schedule is clean
    l2_penalty = min(l2_penalty, 0.5)

    # L3: average model score across assignments → normalized to [0, 1]
    avg_ml = ml_score_sum / total_assignments if total_assignments > 0 else 0.0

    # L5: average LLM score → normalized to [0, 1]
    if llm_overrides and total_assignments > 0:
        avg_llm = llm_score_sum / total_assignments
    else:
        avg_llm = 1.0  # no LLM constraints → neutral

    # ── Blend ──
    α = cfg["model_weight"]
    β = cfg["llm_weight"]
    model_part = avg_ml * α
    llm_part = avg_llm * β
    quality = model_part + llm_part - l2_penalty

    return max(0.0, min(1.0, quality))


# ── L5: LLM override evaluation ─────────────────────────────


def _llm_evaluate(
    assignment: TemplateAssignment,
    task: AllocationTask,
    gene: TaskGene,
    llm_overrides: list[dict],
    cfg: dict[str, Any],
) -> float:
    """Evaluate a single assignment against all active LLM overrides.

    Returns score contribution [0, 1] — lower = more violated.
    """
    day, period = slot_to_day_period(assignment.slot_id)

    for override in llm_overrides:
        if not _override_active(override):
            continue
        if not _scope_matches(override, task):
            continue

        if override.get("type") == "slot_penalty":
            slot_ids = override.get("params", {}).get("slot_ids", [])
            if assignment.slot_id in slot_ids:
                priority = override.get("params", {}).get("priority", "normal")
                weight = _priority_weight(priority)
                return 1.0 - weight  # penalize slot

        elif override.get("type") == "classroom_preference":
            pref_type = override.get("params", {}).get("room_type", "")
            mode = override.get("params", {}).get("mode", "prefer")
            room_matches = _room_type_matches(assignment.classroom_id, pref_type)
            if mode == "prefer" and not room_matches:
                return 0.7
            elif mode == "avoid" and room_matches:
                return 0.5

    return 1.0  # no override applies → neutral


def _override_active(override: dict) -> bool:
    from datetime import date
    if not override.get("active", True):
        return False
    expires = override.get("expires_at")
    if expires:
        try:
            if date.fromisoformat(expires) < date.today():
                return False
        except (ValueError, TypeError):
            pass
    return True


def _scope_matches(override: dict, task: AllocationTask) -> bool:
    scope = override.get("scope", {})
    if not scope:
        return True  # scope=all

    scope_type = scope.get("type")
    if scope_type == "teacher":
        return scope.get("teacher_id") == task.teacher_id
    elif scope_type == "course":
        return scope.get("course_type") == getattr(task, "course_type", None)
    elif scope_type == "student_count":
        return task.student_count >= (scope.get("min") or 0)
    elif scope_type == "task":
        return task.task_id in (scope.get("task_ids") or [])
    return True


def _priority_weight(priority: str) -> float:
    mapping = {"critical": 1.0, "strong": 0.8, "normal": 0.5, "mild": 0.2}
    return mapping.get(priority, 0.5)


def _room_type_matches(room_id: int, target_type: str) -> bool:
    """Check if room_id matches target_type (placeholder — needs DB lookup)."""
    if not target_type:
        return True
    # TODO: inject classroom_by_id map instead of inline lookup
    return True


# ── Profile penalty (lightweight, no GA coupling) ──────────


def _profile_penalty(profile: dict | None, slot_id: int) -> tuple[float, dict]:
    """Simplified profile penalty for scoring pipeline.

    Mirrors ga.py's profile_penalty() but without GA dependencies.
    """
    if not profile:
        return 0.0, {}
    day, period = slot_to_day_period(slot_id)
    raw = profile.get("matrix", {}).get(f"{day}_{period}")
    if raw is None:
        return 0.0, {}
    penalty = max(0, min(raw, 100))
    return penalty / 100.0, {"matrix_value": penalty}


# ── Config builder: generation_config → scoring config ─────────


def build_scoring_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    """Convert DB raw_config dict to scoring pipeline config.

    Maps generation_config DB fields to quality_score() config keys.
    Unset or zero fields fall back to DEFAULT_CONFIG values.
    """
    if not raw_config:
        return dict(DEFAULT_CONFIG)

    def _f(name: str) -> float:
        val = raw_config.get(name)
        if val is None:
            return DEFAULT_CONFIG.get(name, 0.0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return DEFAULT_CONFIG.get(name, 0.0)

    # Map all DB fields → scoring config keys
    # Fields without DB columns fall back to DEFAULT_CONFIG.
    config = dict(DEFAULT_CONFIG)

    # Direct DB → config mappings (existing columns)
    config["profile_penalty_scale"] = _f("teacher_profile_penalty_scale") or config["profile_penalty_scale"]
    config["early_period_penalty"] = _f("early_period_penalty") or config["early_period_penalty"]
    config["late_period_penalty"] = _f("late_period_penalty") or config["late_period_penalty"]
    config["weekend_penalty"] = _f("weekend_penalty") or config.get("weekend_penalty", 0.0)

    # Distribution penalty goes to L4 (template enum), not scoring
    # Classroom stickiness → not yet implemented

    # New fields not yet in DB → use defaults (will be added via migration)
    # model_weight, llm_weight, same_day_weight, capacity_waste_penalty,
    # teacher_day_load_penalty, class_day_load_penalty, teacher_overload_penalty

    return config
