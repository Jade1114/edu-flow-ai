"""Build V3 stable task plans from placement-model resource candidates.

This is the second V3 step:
placement candidates JSONL -> per-teaching-task plan JSONL.

Each plan is still local to one teaching task. Global conflict checking and repair
are intentionally left to the next layer.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_PLAN_COUNT = 120
DEFAULT_PLAN_COUNT = 8
WEEK_USAGE_SCORE_SCALE = 0.0005
DEFAULT_TEACHER_PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "profiles" / "v3" / "teacher_profiles_v3.json"


def generate_task_plans_jsonl(
    candidates_path: str | Path,
    *,
    plan_count: int = DEFAULT_PLAN_COUNT,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write one JSONL row per teaching task with multiple complete plan options."""

    source_path = Path(candidates_path)
    if not source_path.exists():
        raise FileNotFoundError(f"candidates file not found: {source_path}")

    plan_count = max(1, min(int(plan_count), MAX_PLAN_COUNT))
    out_dir = Path(output_dir) if output_dir else source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "task_plans.jsonl"
    generated_at = _now_iso()

    candidate_rows = _read_candidate_rows(source_path)
    teacher_profiles = _load_teacher_profiles()
    allocator = WeekUsageAllocator()
    rows: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as target:
        for line_number, candidate_row in candidate_rows:
            row = _build_task_plan_row(
                candidate_row,
                plan_count=plan_count,
                generated_at=generated_at,
                allocator=allocator,
                teacher_profiles=teacher_profiles,
            )
            row["meta"]["source_line_number"] = line_number
            rows.append(row)
            target.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    summary = {
        "allocation_task_id": _first(rows, "allocation_task_id"),
        "source_path": str(source_path),
        "output_path": str(output_path),
        "task_count": len(rows),
        "plan_count_requested": plan_count,
        "empty_plan_task_count": sum(1 for row in rows if not row.get("plans")),
        "teacher_profile_count": len(teacher_profiles),
        "teacher_profile_scored_plan_count": sum(
            1
            for row in rows
            for plan in row.get("plans") or []
            if plan.get("teacher_profile_source") == "teacher_profiles_v3"
        ),
        "week_strategy": "resource_aware_low_usage",
        "generated_at": generated_at,
    }
    (out_dir / "task_plans_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def _build_task_plan_row(
    candidate_row: dict[str, Any],
    *,
    plan_count: int,
    generated_at: str,
    allocator: "WeekUsageAllocator",
    teacher_profiles: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resources = list(candidate_row.get("resources") or [])
    task = dict(candidate_row.get("task") or {})
    total_hours = int(task.get("total_hours") or 0)
    total_sessions = int(task.get("total_sessions") or total_hours // 2)
    allowed_weeks = _allowed_weeks(candidate_row)

    plans: list[dict[str, Any]] = []
    error = None
    if total_sessions <= 0:
        error = "INVALID_TOTAL_SESSIONS"
    elif not allowed_weeks:
        error = "NO_ALLOWED_WEEKS"
    elif not resources:
        error = candidate_row.get("error") or "NO_RESOURCES"
    else:
        plans = _build_plans(
            candidate_row=candidate_row,
            resources=resources,
            allowed_weeks=allowed_weeks,
            total_sessions=total_sessions,
            total_hours=total_hours,
            plan_count=plan_count,
            allocator=allocator,
            teacher_profiles=teacher_profiles or {},
        )
        if not plans:
            error = "NO_PLANS"

    row = {
        "allocation_task_id": candidate_row.get("allocation_task_id"),
        "teaching_task_id": candidate_row.get("teaching_task_id"),
        "input": candidate_row.get("input") or {},
        "task": task,
        "plans": plans,
        "meta": {
            "source": "v3_plan_templates",
            "placement_candidate_top_k": (candidate_row.get("meta") or {}).get("top_k"),
            "allowed_weeks": allowed_weeks,
            "plan_count_requested": plan_count,
            "plan_count": len(plans),
            "week_strategy": "resource_aware_low_usage",
            "generated_at": generated_at,
        },
    }
    if error:
        row["error"] = error
    return row


def _build_plans(
    *,
    candidate_row: dict[str, Any],
    resources: list[dict[str, Any]],
    allowed_weeks: list[int],
    total_sessions: int,
    total_hours: int,
    plan_count: int,
    allocator: "WeekUsageAllocator",
    teacher_profiles: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    max_distinct_plans = plan_count
    for plan_index in range(max_distinct_plans):
        segments = _build_segments(
            resources=resources,
            allowed_weeks=allowed_weeks,
            total_sessions=total_sessions,
            plan_index=plan_index,
            allocator=allocator,
        )
        if not segments:
            continue
        week_usage_cost = _segments_week_usage_cost(segments)
        teacher_id = int((candidate_row.get("task") or {}).get("teacher_id") or 0)
        profile_metrics = _teacher_profile_metrics(
            segments,
            total_sessions,
            teacher_profiles.get(teacher_id),
        )
        plan = {
            "plan_id": f"{candidate_row.get('teaching_task_id')}_p{plan_index + 1:03d}",
            "plan_rank": len(plans) + 1,
            "segments": segments,
            "total_sessions": total_sessions,
            "total_hours": total_hours,
            "score": _plan_score(segments, total_sessions, week_usage_cost=week_usage_cost),
            "teacher_profile_score": profile_metrics["score"],
            "teacher_profile_penalty": profile_metrics["penalty"],
            "teacher_profile_components": profile_metrics["components"],
            "teacher_profile_reasons": profile_metrics["reasons"],
            "teacher_profile_source": profile_metrics["source"],
            "week_strategy": "resource_aware_low_usage",
            "week_usage_cost": week_usage_cost,
            "valid": _segment_session_sum(segments) == total_sessions,
        }
        plans.append(plan)
    return plans


def _build_segments(
    *,
    resources: list[dict[str, Any]],
    allowed_weeks: list[int],
    total_sessions: int,
    plan_index: int,
    allocator: "WeekUsageAllocator",
) -> list[dict[str, Any]]:
    remaining = total_sessions
    segments: list[dict[str, Any]] = []
    used_slots: set[tuple[int, int]] = set()
    segment_index = 0
    main_resource_index = plan_index

    while remaining > 0 and segment_index < len(resources):
        if segment_index == 0:
            preferred_index = main_resource_index
        else:
            preferred_index = main_resource_index + segment_index + plan_index
        resource = _pick_resource(resources, preferred_index, avoid_slots=used_slots)
        if resource is None:
            break
        slot_key = _slot_key(resource)
        if slot_key:
            used_slots.add(slot_key)

        window_size = min(remaining, len(allowed_weeks))
        resource_key = _resource_key(resource)
        weeks, week_usage_cost = allocator.select_weeks(
            resource_key,
            allowed_weeks,
            window_size,
            plan_index=plan_index,
            segment_index=segment_index,
        )
        allocator.reserve(resource_key, weeks)
        segment_index += 1
        segments.append({
            "template_id": f"t{segment_index}",
            "resource_rank": resource.get("rank"),
            "resource": resource,
            "weeks": weeks,
            "session_count": len(weeks),
            "week_strategy": "resource_aware_low_usage",
            "week_usage_cost": week_usage_cost,
            "resource_key": resource_key,
        })
        remaining -= len(weeks)

    if remaining > 0:
        return []
    return segments


class WeekUsageAllocator:
    """Choose low-usage week masks for each placement resource."""

    def __init__(self) -> None:
        self._usage: dict[str, dict[int, int]] = {}

    def select_weeks(
        self,
        resource_key: str,
        allowed_weeks: list[int],
        size: int,
        *,
        plan_index: int,
        segment_index: int,
    ) -> tuple[list[int], float]:
        candidates = _week_mask_candidates(allowed_weeks, size, plan_index=plan_index, segment_index=segment_index)
        usage = self._usage.setdefault(resource_key, {})
        midpoint = (allowed_weeks[0] + allowed_weeks[-1]) / 2 if allowed_weeks else 0.0

        def key(weeks: list[int]) -> tuple[float, float, float, tuple[int, ...]]:
            usage_cost = sum(usage.get(week, 0) for week in weeks)
            balance_penalty = abs((_avg(weeks) if weeks else 0.0) - midpoint) * 0.02
            front_penalty = sum(max(0, midpoint - week) for week in weeks) * 0.001
            return (usage_cost + balance_penalty + front_penalty, usage_cost, _gap_penalty(weeks), tuple(weeks))

        ranked = sorted(candidates, key=key)
        diversity_window = min(len(ranked), 12)
        selected = (
            ranked[(plan_index + segment_index * 3) % diversity_window]
            if diversity_window
            else []
        )
        return selected, round(key(selected)[0], 6)

    def reserve(self, resource_key: str, weeks: list[int]) -> None:
        usage = self._usage.setdefault(resource_key, {})
        for week in weeks:
            usage[week] = usage.get(week, 0) + 1


def _week_mask_candidates(
    allowed_weeks: list[int],
    size: int,
    *,
    plan_index: int,
    segment_index: int,
) -> list[list[int]]:
    if size <= 0 or not allowed_weeks:
        return []
    weeks = list(allowed_weeks)
    if size >= len(weeks):
        return [weeks]

    candidates: list[list[int]] = []
    max_offset = len(weeks) - size
    for offset in range(max_offset + 1):
        candidates.append(weeks[offset: offset + size])

    for stride in (2, 3, 4):
        for offset in range(stride):
            spaced = weeks[offset::stride]
            if len(spaced) >= size:
                candidates.append(spaced[:size])

    rotation = (plan_index * 3 + segment_index * 5) % len(weeks)
    rotated = weeks[rotation:] + weeks[:rotation]
    candidates.append(sorted(rotated[:size]))
    candidates.append(_least_front_loaded(weeks, size))
    return _unique_week_masks(candidates)


def _least_front_loaded(weeks: list[int], size: int) -> list[int]:
    if size >= len(weeks):
        return list(weeks)
    midpoint = (weeks[0] + weeks[-1]) / 2
    ranked = sorted(weeks, key=lambda week: (abs(week - midpoint), week))
    return sorted(ranked[:size])


def _unique_week_masks(candidates: list[list[int]]) -> list[list[int]]:
    seen: set[tuple[int, ...]] = set()
    result: list[list[int]] = []
    for candidate in candidates:
        normalized = tuple(sorted({int(week) for week in candidate if int(week) > 0}))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(list(normalized))
    return result


def _avg(values: list[int]) -> float:
    return sum(values) / max(1, len(values))


def _gap_penalty(weeks: list[int]) -> float:
    if len(weeks) <= 1:
        return 0.0
    gaps = [right - left for left, right in zip(weeks, weeks[1:])]
    return max(gaps) - min(gaps)


def _pick_resource(
    resources: list[dict[str, Any]],
    preferred_index: int,
    *,
    avoid_slots: set[tuple[int, int]],
) -> dict[str, Any] | None:
    if not resources:
        return None
    for offset in range(len(resources)):
        resource = resources[(preferred_index + offset) % len(resources)]
        slot_key = _slot_key(resource)
        if not slot_key or slot_key not in avoid_slots:
            return resource
    return resources[preferred_index % len(resources)]


def _week_offset(plan_index: int, segment_index: int, week_count: int, window_size: int) -> int:
    if window_size >= week_count:
        return 0
    movable = week_count - window_size + 1
    return (plan_index + segment_index * 2) % movable


def _week_window(allowed_weeks: list[int], size: int, offset: int) -> list[int]:
    if size <= 0:
        return []
    if size >= len(allowed_weeks):
        return list(allowed_weeks)
    return list(allowed_weeks[offset: offset + size])


def _read_candidate_rows(source_path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with source_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            raw = line.strip()
            if raw:
                rows.append((line_number, json.loads(raw)))
    return rows


def _resource_key(resource: dict[str, Any]) -> str:
    slot = resource.get("slot") or {}
    classroom = resource.get("classroom") or {}
    cid = classroom.get("id")
    if cid is None:
        cid = hash(classroom.get("name", "")) % 100000 + 1
    classroom_id = int(cid or 0)
    day = int(slot.get("day_of_week") or 0)
    period = int(slot.get("period_index") or 0)
    return f"{classroom_id}|{day}|{period}"


def _segments_week_usage_cost(segments: list[dict[str, Any]]) -> float:
    return round(sum(float(segment.get("week_usage_cost") or 0.0) for segment in segments), 6)


def _load_teacher_profiles(path: str | Path | None = None) -> dict[int, dict[str, Any]]:
    source_path = Path(path) if path else DEFAULT_TEACHER_PROFILE_PATH
    if not source_path.exists():
        return {}
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    profiles: dict[int, dict[str, Any]] = {}
    for row in payload.get("profiles") or []:
        try:
            teacher_id = int(row.get("teacher_id") or 0)
        except (TypeError, ValueError):
            continue
        final_profile = row.get("final_profile") or {}
        if teacher_id > 0 and isinstance(final_profile, dict):
            profiles[teacher_id] = final_profile
    return profiles


def _teacher_profile_metrics(
    segments: list[dict[str, Any]],
    total_sessions: int,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    if not profile:
        return {
            "score": 1.0,
            "penalty": 0.0,
            "components": {},
            "reasons": [],
            "source": "none",
        }

    sessions = _segment_sessions(segments)
    total = max(1, len(sessions) or total_sessions)
    preferred_weekdays = _int_set(profile.get("preferred_weekdays"))
    preferred_periods = _int_set(profile.get("preferred_periods"))
    preferred_room_types = {str(value).strip() for value in profile.get("preferred_room_types") or [] if str(value).strip()}
    max_daily_lessons = _positive_int(profile.get("max_daily_lessons"))

    early_count = sum(1 for session in sessions if session["period"] == 1)
    late_count = sum(1 for session in sessions if session["period"] >= 5)
    weekday_hits = sum(1 for session in sessions if session["day"] in preferred_weekdays)
    period_hits = sum(1 for session in sessions if session["period"] in preferred_periods)
    room_hits = sum(1 for session in sessions if session["room_type"] in preferred_room_types)

    daily_loads: Counter[tuple[int, int]] = Counter((session["week"], session["day"]) for session in sessions)
    overloaded_days = sum(1 for load in daily_loads.values() if max_daily_lessons > 0 and load > max_daily_lessons)

    components = {
        "early_period": 1.0 - early_count / total if bool(profile.get("avoid_early_period")) else 1.0,
        "late_period": 1.0 - late_count / total if bool(profile.get("avoid_late_period")) else 1.0,
        "preferred_weekday": weekday_hits / total if preferred_weekdays else 1.0,
        "preferred_period": period_hits / total if preferred_periods else 1.0,
        "daily_load": 1.0 - overloaded_days / max(1, len(daily_loads)) if max_daily_lessons > 0 and daily_loads else 1.0,
        "room_type": room_hits / total if preferred_room_types else 1.0,
    }
    components = {key: round(max(0.0, min(1.0, value)), 6) for key, value in components.items()}
    score = round(sum(components.values()) / max(1, len(components)), 6)
    reasons = _teacher_profile_reasons(
        profile,
        components,
        early_count=early_count,
        late_count=late_count,
        weekday_hits=weekday_hits,
        period_hits=period_hits,
        room_hits=room_hits,
        total=total,
        overloaded_days=overloaded_days,
    )
    return {
        "score": score,
        "penalty": round(1.0 - score, 6),
        "components": components,
        "reasons": reasons,
        "source": "teacher_profiles_v3",
    }


def _segment_sessions(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for segment in segments:
        resource = segment.get("resource") or {}
        slot = resource.get("slot") or {}
        classroom = resource.get("classroom") or {}
        day = int(slot.get("day_of_week") or 0)
        period = int(slot.get("period_index") or 0)
        room_type = str(classroom.get("classroom_type") or "").strip()
        for week in segment.get("weeks") or []:
            sessions.append({
                "week": int(week),
                "day": day,
                "period": period,
                "room_type": room_type,
            })
    return sessions


def _teacher_profile_reasons(
    profile: dict[str, Any],
    components: dict[str, float],
    *,
    early_count: int,
    late_count: int,
    weekday_hits: int,
    period_hits: int,
    room_hits: int,
    total: int,
    overloaded_days: int,
) -> list[str]:
    reasons: list[str] = []
    if bool(profile.get("avoid_early_period")):
        reasons.append("避开第1节" if early_count == 0 else f"第1节出现 {early_count}/{total}")
    if bool(profile.get("avoid_late_period")):
        reasons.append("避开晚课" if late_count == 0 else f"晚课出现 {late_count}/{total}")
    if profile.get("preferred_weekdays"):
        reasons.append(f"偏好星期命中 {weekday_hits}/{total}")
    if profile.get("preferred_periods"):
        reasons.append(f"偏好节次命中 {period_hits}/{total}")
    if _positive_int(profile.get("max_daily_lessons")) > 0:
        reasons.append("未超过日课时上限" if overloaded_days == 0 else f"超日课时上限 {overloaded_days} 天")
    if profile.get("preferred_room_types"):
        reasons.append(f"偏好教室类型命中 {room_hits}/{total}")
    return [reason for reason in reasons if reason]


def _int_set(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    result: set[int] = set()
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            result.add(parsed)
    return result


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _plan_score(segments: list[dict[str, Any]], total_sessions: int, *, week_usage_cost: float = 0.0) -> float:
    weighted = 0.0
    for segment in segments:
        resource = segment.get("resource") or {}
        weighted += float(resource.get("score") or 0.0) * int(segment.get("session_count") or 0)
    score = weighted / max(1, total_sessions)
    segment_penalty = max(0, len(segments) - 1) * 0.001
    week_penalty = float(week_usage_cost) * WEEK_USAGE_SCORE_SCALE
    return round(max(0.0, score - segment_penalty - week_penalty), 6)


def _segment_session_sum(segments: list[dict[str, Any]]) -> int:
    return sum(int(segment.get("session_count") or 0) for segment in segments)


def _allowed_weeks(candidate_row: dict[str, Any]) -> list[int]:
    meta = candidate_row.get("meta") or {}
    raw_weeks = meta.get("allowed_weeks") or list(range(1, 19))
    return sorted({int(week) for week in raw_weeks if int(week) > 0})


def _slot_key(resource: dict[str, Any]) -> tuple[int, int] | None:
    slot = resource.get("slot") or {}
    day = int(slot.get("day_of_week") or 0)
    period = int(slot.get("period_index") or 0)
    if day <= 0 or period <= 0:
        return None
    return day, period


def _first(rows: list[dict[str, Any]], key: str) -> Any:
    return rows[0].get(key) if rows else None


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V3 stable task plan JSONL.")
    parser.add_argument("candidates_path")
    parser.add_argument("--plan-count", type=int, default=DEFAULT_PLAN_COUNT)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    summary = generate_task_plans_jsonl(
        args.candidates_path,
        plan_count=args.plan_count,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
