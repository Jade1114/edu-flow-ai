"""Class conflict resolver for V3 scheduling.

After teacher-group solving, checks for cross-group conflicts where
two different teachers' tasks occupy the same class at the same time.

Resolves greedily: most constrained classes (fewest remaining slots) first.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def resolve_class_conflicts(
    *,
    assignments: list[dict],
    task_plans: list[dict],
    class_groups: dict[str, dict],
) -> list[dict]:
    """Resolve class conflicts across teacher groups.

    Args:
        assignments: Output from teacher group solver.
        task_plans: Original task plans (with alternative plan options).
        class_groups: Dict of class_group_name → class_group_info.

    Returns:
        Resolved assignments with reduced class conflicts.
    """
    # Build task → all plan options lookup
    task_plan_map: dict[int, dict] = {}
    for tp in task_plans:
        tid = tp.get("teaching_task_id")
        if tid and not tp.get("error"):
            task_plan_map[tid] = tp

    # Build class_group → assignments mapping
    # And collect all slots per class
    class_slots: dict[int, dict[tuple[int, int, int], list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    # class_slots[cg_id][(week, day, period)] = [assignment_index, ...]

    # Map assignment items by index for quick lookup
    for ai, a in enumerate(assignments):
        for item in a.get("items", []):
            cids = item.get("class_group_ids", [])
            week = int(item.get("week_number", 0))
            day = int(item.get("day_of_week", 0))
            period = int(item.get("period_index", 0))
            if not week or not day or not period:
                continue
            for cid in cids:
                class_slots[cid][(week, day, period)].append(ai)

    # Find conflicting class slots
    conflicts = []
    for cid, slots in class_slots.items():
        for key, assignment_indices in slots.items():
            if len(assignment_indices) > 1:
                # class cid has a conflict at this slot
                conflicts.append((cid, key, assignment_indices))

    if not conflicts:
        return assignments

    # Sort conflicts: most conflicts per class first
    class_conflict_count: dict[int, int] = defaultdict(int)
    for cid, _, indices in conflicts:
        class_conflict_count[cid] += len(indices) - 1

    # Process classes by conflict count (most conflicted first)
    processed_assignments = {i for i in range(len(assignments))}
    resolved_assignments = list(assignments)  # mutable copy

    for cid in sorted(class_conflict_count, key=lambda c: -class_conflict_count[c]):
        # Find all slots for this class
        for (week, day, period), a_indices in class_slots[cid].items():
            if len(a_indices) <= 1:
                continue
            # Keep the assignment with better score, try to move others
            best_idx = a_indices[0]
            best_score = float(resolved_assignments[best_idx].get("score", 0))

            for ai in a_indices[1:]:
                # Try to move this assignment's task to a different plan
                a = resolved_assignments[ai]
                tid = a.get("teaching_task_id")
                if not tid or tid not in task_plan_map:
                    continue

                tp = task_plan_map[tid]
                plans = tp.get("plans", [])
                if len(plans) <= 1:
                    continue  # no alternatives

                # Try alternative plans
                moved = False
                for plan in sorted(plans, key=lambda p: -float(p.get("score", 0))):
                    plan_id = plan.get("plan_id", "")
                    if plan_id == a.get("plan_id", ""):
                        continue  # same plan
                    if not plan.get("valid", True):
                        continue

                    # Check if this plan avoids the current class conflict
                    # AND doesn't introduce new conflicts
                    new_items = _plan_to_items_for_assignment(tp, plan)
                    if not new_items:
                        continue

                    # Check this specific class slot
                    slot_clear = True
                    for item in new_items:
                        i_cids = item.get("class_group_ids", [])
                        i_week = int(item.get("week_number", 0))
                        i_day = int(item.get("day_of_week", 0))
                        i_period = int(item.get("period_index", 0))
                        if cid in i_cids and i_week == week and i_day == day and i_period == period:
                            slot_clear = False
                            break

                    if not slot_clear:
                        continue

                    # Also check teacher conflicts
                    teacher_conflict = False
                    for item in new_items:
                        tw = int(item.get("week_number", 0))
                        td = int(item.get("day_of_week", 0))
                        tp_ = int(item.get("period_index", 0))
                        # Check against other resolved assignments
                        for oi, oa in enumerate(resolved_assignments):
                            if oi == ai:
                                continue
                            for oitem in oa.get("items", []):
                                if (oitem.get("teacher_id") == item.get("teacher_id") and
                                    int(oitem.get("week_number", 0)) == tw and
                                    int(oitem.get("day_of_week", 0)) == td and
                                    int(oitem.get("period_index", 0)) == tp_):
                                    teacher_conflict = True
                                    break
                            if teacher_conflict:
                                break
                        if teacher_conflict:
                            break

                    if teacher_conflict:
                        continue

                    # Accept this plan
                    resolved_assignments[ai] = {
                        "teaching_task_id": tid,
                        "teacher_name": a.get("teacher_name"),
                        "teacher_id": a.get("teacher_id"),
                        "items": new_items,
                        "plan_id": plan_id,
                        "score": float(plan.get("score", 0)),
                        "task_count": a.get("task_count", 1),
                    }
                    moved = True
                    break

                if not moved:
                    # Accept the conflict as unavoidable
                    pass

    return resolved_assignments


def _plan_to_items_for_assignment(task_plan: dict, plan: dict) -> list[dict]:
    """Same as teacher_group_solver._plan_to_items but standalone."""
    task_info = task_plan.get("task") or {}
    teaching_task_id = task_plan.get("teaching_task_id") or task_info.get("teaching_task_id")
    teacher_id = task_info.get("teacher_id")
    class_group_ids = task_info.get("class_group_ids") or []

    items = []
    for segment in plan.get("segments", []):
        resource = segment.get("resource") or {}
        slot = resource.get("slot") or {}
        classroom = resource.get("classroom") or {}
        day = int(slot.get("day_of_week", 0))
        period = int(slot.get("period_index", 0))
        room_name = classroom.get("name", "")
        room_id = classroom.get("id")

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
                "placement_score": float(resource.get("score", 0)),
                "selected_plan_id": plan.get("plan_id", ""),
                "template_id": segment.get("template_id", ""),
            })

    return items
