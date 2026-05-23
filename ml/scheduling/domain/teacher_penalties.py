"""Teacher-penalty normalization and presentation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_unavailable_slots(raw_slots: Any) -> list[list[int]]:
    normalized: list[list[int]] = []
    if not raw_slots:
        return normalized
    for slot in raw_slots:
        if isinstance(slot, (list, tuple)) and len(slot) >= 2:
            try:
                normalized.append([int(slot[0]), int(slot[1])])
            except (TypeError, ValueError):
                continue
    return sorted(normalized)


def normalize_teacher_penalties(raw: dict[str, Any]) -> dict[int, dict[str, Any]]:
    payload = raw.get("teacher_penalties", raw)
    penalties: dict[int, dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return penalties
    for teacher_key, value in payload.items():
        if not isinstance(value, dict):
            continue
        try:
            teacher_id = int(value.get("teacher_id") or teacher_key)
        except (TypeError, ValueError):
            continue
        penalties[teacher_id] = {
            "unavailable_slots": normalize_unavailable_slots(value.get("unavailable_slots")),
            "max_weekly_hours": int(value["max_weekly_hours"]) if value.get("max_weekly_hours") is not None else None,
            "penalty_weight": float(value.get("penalty_weight") or 0.05),
            "reason": str(value.get("reason") or value.get("note") or ""),
            "profile_preference": value.get("profile_preference") if isinstance(value.get("profile_preference"), dict) else {},
        }
    return penalties


def build_teacher_penalties_from_profiles(teacher_profiles: dict[int, dict[str, object]]) -> dict[int, dict[str, Any]]:
    return {
        teacher_id: {
            "unavailable_slots": normalize_unavailable_slots(profile.get("unavailable_slots")),
            "max_weekly_hours": profile.get("max_weekly_hours"),
            "penalty_weight": 0.05,
            "reason": "MySQL teacher_profile",
            "profile_preference": profile.get("profile_preference") if isinstance(profile.get("profile_preference"), dict) else {},
        }
        for teacher_id, profile in teacher_profiles.items()
    }


def summarize_teacher_penalties(penalties: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "teacher_count": len(penalties),
        "teachers": [
            {
                "teacher_id": teacher_id,
                "unavailable_slots": penalty.get("unavailable_slots") or [],
                "max_weekly_hours": penalty.get("max_weekly_hours"),
                "penalty_weight": penalty.get("penalty_weight"),
                "reason": penalty.get("reason"),
            }
            for teacher_id, penalty in sorted(penalties.items())
        ],
    }


def load_teacher_penalties(path: Path) -> dict[int, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_teacher_penalties(payload)


def write_teacher_penalties(penalties: dict[int, dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"teacher_penalties": {str(key): value for key, value in sorted(penalties.items())}}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_teacher_profile_penalty_explanation(best: dict[str, Any]) -> str:
    breakdown = best.get("teacher_profile_penalty_breakdown") or []
    if not breakdown:
        return ""
    parts: list[str] = []
    for item in breakdown:
        penalty = item.get("penalty")
        reason = item.get("reason") or "教师画像约束"
        if item.get("type") == "unavailable_slot":
            parts.append(
                f"教师画像扣分 {penalty}：周{item.get('day_of_week')}第{item.get('period_index')}节命中不可用时间；{reason}"
            )
        elif item.get("type") == "max_weekly_hours_exceeded":
            parts.append(
                f"教师画像扣分 {penalty}：周课时 {item.get('teacher_week_load_before')}+1 超过偏好上限 {item.get('max_weekly_hours')}；{reason}"
            )
        else:
            parts.append(f"教师画像扣分 {penalty}：{reason}")
    return "；".join(parts)
