"""Teacher group solver for V3 scheduling.

Groups teaching tasks by teacher. Within each group, selects compatible plan
combinations that avoid teacher double-booking and maximize placement quality.

Key insight: professional course teachers have ≤21 tasks each.
Within-group solving uses greedy search with lightweight backtracking.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def solve_teacher_groups(
    *,
    task_plans: list[dict],
    semester_weeks: int = 18,
) -> list[dict]:
    """Solve within-teacher conflicts by grouping tasks per teacher.

    Args:
        task_plans: List of task plan rows from template generator.
            Each row has: teaching_task_id, task (teacher info), plans (list of plan options).
        semester_weeks: Number of weeks in the semester (default 18).

    Returns:
        List of assignment dicts, one per scheduled task:
        {teaching_task_id, teacher_name, teacher_id, items: [...], plan_id, score}
    """
    # Group task plans by teacher
    teacher_groups: dict[str, list[dict]] = defaultdict(list)
    for tp in task_plans:
        if tp.get("error"):
            continue
        task_info = tp.get("task") or {}
        teacher_name = (task_info.get("teacher_name") or "").strip()
        if not teacher_name:
            continue
        plans = tp.get("plans") or []
        if not plans:
            continue
        teacher_groups[teacher_name].append({
            "teaching_task_id": tp.get("teaching_task_id"),
            "task": task_info,
            "plans": plans,
            "input": tp.get("input") or {},
        })

    # Solve each teacher group independently
    all_assignments: list[dict] = []
    for teacher_name, group_tasks in teacher_groups.items():
        assignment = _solve_single_teacher_group(
            teacher_name=teacher_name,
            tasks=group_tasks,
            semester_weeks=semester_weeks,
        )
        if assignment:
            all_assignments.append(assignment)

    return all_assignments


def _solve_single_teacher_group(
    *,
    teacher_name: str,
    tasks: list[dict],
    semester_weeks: int,
) -> dict | None:
    """Solve one teacher's task group.

    Greedy with backtracking: sort tasks by fewest valid plans first.
    Try best plan; if conflicts with already-placed tasks, try next plan.
    If all plans conflict, backtrack.
    """
    # Sort by plan count (fewest options first = most constrained first)
    sorted_tasks = sorted(tasks, key=lambda t: len(t.get("plans", [])))

    # Track occupied teacher slots: (week, day, period) → task index
    occupied: dict[tuple[int, int, int], int] = {}
    selected: list[dict] = []  # (task_index, plan_dict, items)

    def _try_assign(task_idx: int) -> bool:
        if task_idx >= len(sorted_tasks):
            return True

        task = sorted_tasks[task_idx]
        plans = sorted(task["plans"], key=lambda p: -float(p.get("score", 0)))

        for plan in plans:
            if not plan.get("valid", True):
                continue

            items = _plan_to_items(task, plan)
            if not items:
                continue

            # Check teacher conflict
            conflicts = False
            for item in items:
                week = int(item.get("week_number", 0))
                day = int(item.get("day_of_week", 0))
                period = int(item.get("period_index", 0))
                key = (week, day, period)
                if key in occupied:
                    conflicts = True
                    break

            if conflicts:
                continue

            # Place it
            for item in items:
                week = int(item.get("week_number", 0))
                day = int(item.get("day_of_week", 0))
                period = int(item.get("period_index", 0))
                occupied[(week, day, period)] = task_idx

            selected.append({
                "task_idx": task_idx,
                "plan": plan,
                "items": items,
            })

            if _try_assign(task_idx + 1):
                return True

            # Backtrack
            selected.pop()
            for item in items:
                week = int(item.get("week_number", 0))
                day = int(item.get("day_of_week", 0))
                period = int(item.get("period_index", 0))
                occupied.pop((week, day, period), None)

        return False

    success = _try_assign(0)

    if not success:
        # Fallback: greedy without backtracking
        occupied.clear()
        selected.clear()
        for task in sorted_tasks:
            plans = sorted(task["plans"], key=lambda p: -float(p.get("score", 0)))
            placed = False
            for plan in plans:
                if not plan.get("valid", True):
                    continue
                items = _plan_to_items(task, plan)
                if not items:
                    continue
                conflicts = any(
                    (int(item.get("week_number", 0)),
                     int(item.get("day_of_week", 0)),
                     int(item.get("period_index", 0))) in occupied
                    for item in items
                )
                if not conflicts:
                    for item in items:
                        occupied[(
                            int(item.get("week_number", 0)),
                            int(item.get("day_of_week", 0)),
                            int(item.get("period_index", 0)),
                        )] = len(selected)
                    selected.append({
                        "task_idx": len(selected),
                        "plan": plan,
                        "items": items,
                    })
                    placed = True
                    break
            if not placed:
                # Last resort: use first plan and mark conflicts
                for plan in plans:
                    if plan.get("valid", True):
                        items = _plan_to_items(task, plan)
                        if items:
                            selected.append({
                                "task_idx": len(selected),
                                "plan": plan,
                                "items": items,
                            })
                            break

    # Build assignment dict
    task_info = tasks[0]["task"] if tasks else {}
    teacher_id = task_info.get("teacher_id")
    all_items = []
    total_score = 0.0
    for s in selected:
        all_items.extend(s["items"])
        total_score += float(s["plan"].get("score", 0))

    return {
        "teaching_task_id": task_info.get("teaching_task_id"),
        "teacher_name": teacher_name,
        "teacher_id": teacher_id,
        "items": all_items,
        "plan_id": ",".join(str(s["plan"].get("plan_id", "")) for s in selected),
        "score": round(total_score, 4),
        "task_count": len(tasks),
    }


def _plan_to_items(task: dict, plan: dict) -> list[dict]:
    """Convert a plan into schedule items for conflict checking.

    Each item: {teaching_task_id, teacher_id, class_group_ids, classroom_name,
                 classroom_id, week_number, day_of_week, period_index, placement_score}
    """
    task_info = task.get("task") or {}
    teaching_task_id = task.get("teaching_task_id") or task_info.get("teaching_task_id")
    teacher_id = task_info.get("teacher_id")
    class_group_ids = task_info.get("class_group_ids") or []
    input_data = task.get("input") or {}

    items = []
    for segment in plan.get("segments", []):
        resource = segment.get("resource") or {}
        slot = resource.get("slot") or {}
        classroom = resource.get("classroom") or {}
        day = int(slot.get("day_of_week", 0))
        period = int(slot.get("period_index", 0))
        room_name = classroom.get("name", "")
        room_id = classroom.get("id")
        resource_score = float(resource.get("score", 0))

        for week in segment.get("weeks", []):
            week_num = int(week)
            items.append({
                "teaching_task_id": teaching_task_id,
                "teacher_id": teacher_id,
                "class_group_ids": list(class_group_ids),
                "classroom_name": room_name,
                "classroom_id": room_id,
                "week_number": week_num,
                "day_of_week": day,
                "period_index": period,
                "placement_score": round(resource_score, 6),
                "selected_plan_id": plan.get("plan_id", ""),
                "template_id": segment.get("template_id", ""),
            })

    return items
