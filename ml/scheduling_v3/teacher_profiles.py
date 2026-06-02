"""V3 teacher profile derivation and timetable satisfaction analysis.

This module is intentionally an analysis layer. It does not change the V3
placement model or CP-SAT objective. The profile is a structured knowledge asset
that can later be consumed by scheduling, reporting, and model features.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_DATASET_DIR = PROJECT_ROOT / "data" / "real-dataset"
DEFAULT_PROFILE_OUTPUT = PROJECT_ROOT / "data" / "profiles" / "v3" / "teacher_profiles_v3.json"
DEFAULT_REPORT_OUTPUT = PROJECT_ROOT / "data" / "profiles" / "v3" / "teacher_profile_satisfaction_report.json"

EARLY_PERIOD = 1
LATE_PERIODS = {5}
MIN_OBSERVATIONS_FOR_AVOID = 10
AVOID_RATE_THRESHOLD = 0.05


def derive_profiles_from_real_dataset(
    data_dir: Path = REAL_DATASET_DIR,
    *,
    output_path: Path | None = DEFAULT_PROFILE_OUTPUT,
    include_db_ids: bool = True,
) -> dict[str, Any]:
    """Derive baseline teacher profiles from cleaned historical timetable data."""

    classrooms = _load_classrooms(data_dir / "classrooms_clean.jsonl")
    teaching_tasks = _load_teaching_task_teacher_index(data_dir / "teaching_tasks_clean.jsonl")
    teacher_ids = _load_teacher_ids_from_db() if include_db_ids else {}

    stats: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(data_dir / "timetables_clean.jsonl"):
        course_code = str(row.get("course_code") or "").strip()
        class_group = str(row.get("class_group") or "").strip()
        teacher_name = teaching_tasks.get((course_code, class_group))
        if not teacher_name:
            continue

        week = _to_int(row.get("week"))
        day = _to_int(row.get("day"))
        period = _period_index(row)
        room_name = str(row.get("room") or "").strip()
        room = classrooms.get(room_name, {})
        room_type = str(room.get("classroom_type") or "").strip() or "unknown"

        if week <= 0 or day <= 0 or period <= 0:
            continue

        teacher = stats.setdefault(teacher_name, _empty_teacher_stats(teacher_name, teacher_ids.get(teacher_name)))
        teacher["total_sessions"] += 1
        teacher["weekday_counts"][day] += 1
        teacher["period_counts"][period] += 1
        teacher["day_period_counts"][f"{day}-{period}"] += 1
        teacher["room_type_counts"][room_type] += 1
        teacher["daily_loads"][(week, day)] += 1
        teacher["weekly_active_days"][week].add(day)

    profiles = [_build_profile(teacher) for teacher in stats.values()]
    profiles.sort(key=lambda item: (item.get("teacher_name") or "", item.get("teacher_id") or 0))

    result = {
        "profile_version": "v3_baseline_derived_from_real_timetable",
        "generated_at": _now_iso(),
        "source": {
            "data_dir": str(data_dir),
            "timetable_file": "timetables_clean.jsonl",
            "teacher_id_source": "database" if teacher_ids else "not_available",
        },
        "teacher_count": len(profiles),
        "profiles": profiles,
    }
    if output_path:
        _write_json(output_path, result)
    return result


def analyze_scheme_satisfaction(
    schemes_path: Path,
    profiles_path: Path = DEFAULT_PROFILE_OUTPUT,
    *,
    data_dir: Path = REAL_DATASET_DIR,
    output_path: Path | None = DEFAULT_REPORT_OUTPUT,
) -> dict[str, Any]:
    """Analyze V3 schemes against derived teacher profiles."""

    profile_doc = json.loads(Path(profiles_path).read_text(encoding="utf-8"))
    profiles = _profiles_by_teacher_id(profile_doc)
    classrooms = _load_classrooms(data_dir / "classrooms_clean.jsonl")

    scheme_reports = []
    for line_number, scheme in enumerate(_read_jsonl(schemes_path), start=1):
        items = list(scheme.get("items") or [])
        by_teacher: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            teacher_id = _to_int(item.get("teacher_id"))
            if teacher_id > 0:
                by_teacher[teacher_id].append(item)

        teacher_reports = []
        for teacher_id, teacher_items in sorted(by_teacher.items()):
            profile = profiles.get(teacher_id)
            if not profile:
                continue
            teacher_reports.append(_score_teacher_items(profile, teacher_items, classrooms))

        teacher_reports.sort(key=lambda item: item["satisfaction_score"])
        summary = _scheme_summary(teacher_reports)
        scheme_reports.append({
            "scheme_index": scheme.get("scheme_index", line_number),
            "item_count": len(items),
            "profiled_teacher_count": len(teacher_reports),
            "summary": summary,
            "low_satisfaction_teachers": teacher_reports[:10],
            "teacher_reports": teacher_reports,
        })

    result = {
        "report_version": "v3_teacher_profile_satisfaction_mvp",
        "generated_at": _now_iso(),
        "schemes_path": str(schemes_path),
        "profiles_path": str(profiles_path),
        "scheme_count": len(scheme_reports),
        "schemes": scheme_reports,
    }
    if output_path:
        _write_json(output_path, result)
    return result


def _empty_teacher_stats(teacher_name: str, teacher_id: int | None) -> dict[str, Any]:
    return {
        "teacher_name": teacher_name,
        "teacher_id": teacher_id,
        "total_sessions": 0,
        "weekday_counts": Counter(),
        "period_counts": Counter(),
        "day_period_counts": Counter(),
        "room_type_counts": Counter(),
        "daily_loads": Counter(),
        "weekly_active_days": defaultdict(set),
    }


def _build_profile(stat: dict[str, Any]) -> dict[str, Any]:
    total = int(stat["total_sessions"])
    daily_load_values = list(stat["daily_loads"].values())
    weekly_active_day_values = [len(days) for days in stat["weekly_active_days"].values()]

    weekday_rates = _rate_map(stat["weekday_counts"], total)
    period_rates = _rate_map(stat["period_counts"], total)
    room_type_rates = _rate_map(stat["room_type_counts"], total)

    preferred_weekdays = _top_keys(stat["weekday_counts"], limit=2)
    common_periods = _top_keys(stat["period_counts"], limit=2)
    common_room_types = [key for key, rate in room_type_rates.items() if rate >= 0.2 and key != "unknown"]
    avg_active_days = mean(weekly_active_day_values) if weekly_active_day_values else 0.0
    compactness_score = _clamp(1.0 - max(0.0, avg_active_days - 1.0) / 4.0)
    max_daily_lessons = int(_percentile(daily_load_values, 0.9) or max(daily_load_values or [0]))

    early_rate = period_rates.get(str(EARLY_PERIOD), 0.0)
    late_rate = sum(period_rates.get(str(period), 0.0) for period in LATE_PERIODS)

    return {
        "teacher_id": stat.get("teacher_id"),
        "teacher_name": stat["teacher_name"],
        "source": "derived_from_real_timetable",
        "observation_count": total,
        "derived_from_data": {
            "early_period_rate": round(early_rate, 4),
            "late_period_rate": round(late_rate, 4),
            "weekday_rates": weekday_rates,
            "period_rates": period_rates,
            "preferred_weekdays": preferred_weekdays,
            "common_periods": common_periods,
            "avg_daily_lessons": round(mean(daily_load_values), 2) if daily_load_values else 0.0,
            "max_observed_daily_lessons": max(daily_load_values or [0]),
            "p90_daily_lessons": max_daily_lessons,
            "avg_weekly_active_days": round(avg_active_days, 2),
            "compactness_score": round(compactness_score, 4),
            "room_type_rates": room_type_rates,
            "common_room_types": common_room_types,
        },
        "final_profile": {
            "avoid_early_period": total >= MIN_OBSERVATIONS_FOR_AVOID and early_rate <= AVOID_RATE_THRESHOLD,
            "avoid_late_period": total >= MIN_OBSERVATIONS_FOR_AVOID and late_rate <= AVOID_RATE_THRESHOLD,
            "prefer_compact_schedule": compactness_score >= 0.7,
            "preferred_weekdays": preferred_weekdays,
            "preferred_periods": common_periods,
            "max_daily_lessons": max_daily_lessons,
            "preferred_room_types": common_room_types,
        },
    }


def _score_teacher_items(
    profile: dict[str, Any],
    items: list[dict[str, Any]],
    classrooms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    final_profile = dict(profile.get("final_profile") or {})
    total = max(1, len(items))
    preferred_weekdays = {int(day) for day in final_profile.get("preferred_weekdays") or []}
    preferred_periods = {int(period) for period in final_profile.get("preferred_periods") or []}
    preferred_room_types = set(final_profile.get("preferred_room_types") or [])
    max_daily_lessons = _to_int(final_profile.get("max_daily_lessons"))

    early_count = sum(1 for item in items if _to_int(item.get("period_index")) == EARLY_PERIOD)
    late_count = sum(1 for item in items if _to_int(item.get("period_index")) in LATE_PERIODS)
    weekday_hits = sum(1 for item in items if _to_int(item.get("day_of_week")) in preferred_weekdays)
    period_hits = sum(1 for item in items if _to_int(item.get("period_index")) in preferred_periods)
    room_type_hits = 0
    if preferred_room_types:
        for item in items:
            room_name = str(item.get("classroom_name") or "").strip()
            room_type = str(classrooms.get(room_name, {}).get("classroom_type") or "").strip()
            if room_type in preferred_room_types:
                room_type_hits += 1

    day_loads: Counter[tuple[int, int]] = Counter()
    for item in items:
        day_loads[(_to_int(item.get("week_number")), _to_int(item.get("day_of_week")))] += 1
    overloaded_days = sum(1 for load in day_loads.values() if max_daily_lessons > 0 and load > max_daily_lessons)

    components = {
        "early_period": 1.0 if not final_profile.get("avoid_early_period") else 1.0 - early_count / total,
        "late_period": 1.0 if not final_profile.get("avoid_late_period") else 1.0 - late_count / total,
        "preferred_weekday": 1.0 if not preferred_weekdays else weekday_hits / total,
        "preferred_period": 1.0 if not preferred_periods else period_hits / total,
        "daily_load": 1.0 if not day_loads or max_daily_lessons <= 0 else 1.0 - overloaded_days / len(day_loads),
        "room_type": 1.0 if not preferred_room_types else room_type_hits / total,
    }
    components = {key: round(_clamp(value), 4) for key, value in components.items()}
    score = round(mean(components.values()), 4)

    return {
        "teacher_id": profile.get("teacher_id"),
        "teacher_name": profile.get("teacher_name"),
        "item_count": len(items),
        "satisfaction_score": score,
        "components": components,
        "evidence": {
            "early_item_count": early_count,
            "late_item_count": late_count,
            "preferred_weekday_hits": weekday_hits,
            "preferred_period_hits": period_hits,
            "overloaded_days": overloaded_days,
            "preferred_room_type_hits": room_type_hits if preferred_room_types else None,
        },
        "profile_used": final_profile,
    }


def _scheme_summary(teacher_reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not teacher_reports:
        return {
            "avg_satisfaction_score": 0.0,
            "teacher_count": 0,
            "low_satisfaction_count": 0,
        }
    scores = [float(report["satisfaction_score"]) for report in teacher_reports]
    return {
        "avg_satisfaction_score": round(mean(scores), 4),
        "teacher_count": len(teacher_reports),
        "low_satisfaction_count": sum(1 for score in scores if score < 0.7),
        "hard_unavailable_violation_count": 0,
        "note": "MVP report covers derived soft preferences only; hard unavailable requires declared profile input.",
    }


def _load_teaching_task_teacher_index(path: Path) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for row in _read_jsonl(path):
        course_code = str(row.get("course_code") or "").strip()
        class_group = str(row.get("class_group") or "").strip()
        teacher = str(row.get("teacher") or "").strip()
        if course_code and class_group and teacher:
            index[(course_code, class_group)] = teacher
    return index


def _load_classrooms(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("name") or "").strip(): row
        for row in _read_jsonl(path)
        if str(row.get("name") or "").strip()
    }


def _load_teacher_ids_from_db() -> dict[str, int]:
    try:
        from ml.db.config import connect, load_db_config
    except Exception:
        return {}
    try:
        conn = connect(load_db_config())
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM teacher")
                return {str(row["name"]).strip(): int(row["id"]) for row in cursor.fetchall() if row.get("name")}
        finally:
            conn.close()
    except Exception:
        return {}


def _profiles_by_teacher_id(profile_doc: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result = {}
    for profile in profile_doc.get("profiles") or []:
        teacher_id = _to_int(profile.get("teacher_id"))
        if teacher_id > 0:
            result[teacher_id] = profile
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _period_index(row: dict[str, Any]) -> int:
    period_start = _to_int(row.get("period_start"))
    if period_start in {1, 3, 5, 7, 9}:
        return {1: 1, 3: 2, 5: 3, 7: 4, 9: 5}[period_start]
    return _to_int(row.get("period_index"))


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _rate_map(counter: Counter, total: int) -> dict[str, float]:
    if total <= 0:
        return {}
    return {str(key): round(value / total, 4) for key, value in sorted(counter.items())}


def _top_keys(counter: Counter, *, limit: int) -> list[int]:
    return [int(key) for key, _ in counter.most_common(limit)]


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return float(ordered[index])


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="V3 teacher profile utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    derive = subparsers.add_parser("derive", help="derive baseline profiles from cleaned real timetable data")
    derive.add_argument("--data-dir", type=Path, default=REAL_DATASET_DIR)
    derive.add_argument("--output", type=Path, default=DEFAULT_PROFILE_OUTPUT)
    derive.add_argument("--no-db-ids", action="store_true", help="do not try to map teacher names to DB ids")

    analyze = subparsers.add_parser("analyze", help="analyze generated schemes against teacher profiles")
    analyze.add_argument("--schemes", type=Path, required=True)
    analyze.add_argument("--profiles", type=Path, default=DEFAULT_PROFILE_OUTPUT)
    analyze.add_argument("--data-dir", type=Path, default=REAL_DATASET_DIR)
    analyze.add_argument("--output", type=Path, default=DEFAULT_REPORT_OUTPUT)

    args = parser.parse_args()
    if args.command == "derive":
        result = derive_profiles_from_real_dataset(
            args.data_dir,
            output_path=args.output,
            include_db_ids=not args.no_db_ids,
        )
        print(json.dumps({"output": str(args.output), "teacher_count": result["teacher_count"]}, ensure_ascii=False))
    elif args.command == "analyze":
        result = analyze_scheme_satisfaction(
            args.schemes,
            args.profiles,
            data_dir=args.data_dir,
            output_path=args.output,
        )
        print(json.dumps({"output": str(args.output), "scheme_count": result["scheme_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
