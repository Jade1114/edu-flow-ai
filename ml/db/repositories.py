"""SQL query helpers used by training sample generation and GA scheduling."""

from __future__ import annotations

from typing import Any

from ml.scheduling.domain.teacher_profile import (
    parse_availability_matrix_unavailable,
    parse_optional_int,
    parse_profile_preference,
)


def fetch_all(connection, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    except Exception as exc:
        import sys as _sys

        preview = " ".join(sql.split())[:120]
        print(
            f"[SCHEDULE-CHAIN] DB error: {preview} | params={params} | {type(exc).__name__}: {exc}",
            file=_sys.stderr,
            flush=True,
        )
        raise


def fetch_tasks(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT
            tt.id AS teaching_task_id,
            tt.primary_teacher_id AS teacher_id,
            t.name AS teacher_name,
            tt.assistant_teacher_id,
            tt.classroom_id AS bound_classroom_id,
            tt.total_hours,
            tt.required_room_type,
            c.course_type,
            c.required_hours AS course_required_hours,
            t.department AS teacher_department,
            t.title AS teacher_title,
            t.max_weekly_hours AS teacher_max_weekly_hours,
            bound_cr.classroom_type AS bound_classroom_type,
            COUNT(cg.id) AS class_group_count,
            COALESCE(SUM(cg.student_count), 0) AS total_student_count,
            GROUP_CONCAT(cg.id ORDER BY cg.id) AS class_group_ids,
            GROUP_CONCAT(cg.major ORDER BY cg.id) AS class_group_majors,
            GROUP_CONCAT(cg.grade ORDER BY cg.id) AS class_group_grades
        FROM teaching_task tt
        JOIN course c ON c.id = tt.course_id
        JOIN teacher t ON t.id = tt.primary_teacher_id
        LEFT JOIN classroom bound_cr ON bound_cr.id = tt.classroom_id
        LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
        LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
        WHERE tt.status = 'ACTIVE'
        GROUP BY
            tt.id,
            tt.primary_teacher_id,
            tt.assistant_teacher_id,
            tt.classroom_id,
            tt.total_hours,
            tt.required_room_type,
            t.name,
            c.course_type,
            c.required_hours,
            t.department,
            t.title,
            t.max_weekly_hours,
            bound_cr.classroom_type
        ORDER BY tt.id
        """,
    )


def fetch_classrooms(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT id, name, building, capacity, classroom_type
        FROM classroom
        WHERE status = 'ACTIVE'
        ORDER BY id
        """,
    )


def fetch_time_slots(connection) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT id, week_number, day_of_week, period_index, label
        FROM time_slot
        ORDER BY week_number, day_of_week, period_index
        """,
    )


def fetch_teacher_profiles(connection) -> dict[int, dict[str, object]]:
    """Return {teacher_id: {unavailable_slots, max_weekly_hours, profile_preference, ...}}."""
    rows = fetch_all(
        connection,
        """
        SELECT p.teacher_id, p.availability_matrix_json,
               p.profile_preference_json,
               t.max_weekly_hours, t.name AS teacher_name,
               t.department
        FROM teacher_profile p
        JOIN teacher t ON t.id = p.teacher_id
        WHERE t.status = 'ACTIVE'
        """,
    )
    profiles: dict[int, dict[str, object]] = {}
    for row in rows:
        teacher_id = int(row["teacher_id"])
        unavailable = parse_availability_matrix_unavailable(row.get("availability_matrix_json") or "")
        parsed_preference = parse_profile_preference(row.get("profile_preference_json") or "")
        max_hours = parse_optional_int(parsed_preference.get("preferredMaxWeeklyHours"))
        if max_hours is None:
            db_max = row.get("max_weekly_hours")
            max_hours = int(db_max) if db_max is not None else None
        profiles[teacher_id] = {
            "unavailable_slots": unavailable,
            "max_weekly_hours": max_hours,
            "profile_preference": parsed_preference,
            "teacher_name": row.get("teacher_name") or "",
            "department": row.get("department") or "",
        }
    return profiles


def fetch_allocation_task(connection, task_id: int) -> dict[str, Any] | None:
    """Get allocation task by id. Returns None if not found."""
    rows = fetch_all(
        connection,
        "SELECT id, name, status FROM allocation_task WHERE id = %s",
        (task_id,),
    )
    for row in rows:
        if int(row["id"]) == task_id:
            return row
    return None


def fetch_task_teaching_task_ids(connection, task_id: int) -> list[int]:
    """Get teaching task ids bound to an allocation task."""
    rows = fetch_all(
        connection,
        "SELECT teaching_task_id FROM allocation_task_teaching_task WHERE allocation_task_id = %s",
        (task_id,),
    )
    return [int(row["teaching_task_id"]) for row in rows]


def fetch_generation_config(connection, task_id: int) -> dict[str, Any] | None:
    """Get generation config for an allocation task. Returns None if not set."""
    rows = fetch_all(
        connection,
        """
        SELECT
            allowed_weeks, allowed_weekdays, allowed_periods,
            scheme_count,
            teacher_profile_penalty_scale,
            early_period_penalty, late_period_penalty, weekend_penalty,
            model_weight, llm_weight,
            same_day_weight, capacity_waste_penalty,
            teacher_day_load_penalty, class_day_load_penalty,
            teacher_overload_penalty
        FROM allocation_task_generation_config
        WHERE task_id = %s
        """,
        (task_id,),
    )
    if not rows:
        return None
    return rows[0]
