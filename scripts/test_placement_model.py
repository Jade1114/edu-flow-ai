"""Test V3 Placement Model on teaching tasks.

Loads the trained LightGBM direct placement model and runs inference
on teaching tasks from the DB, showing TopK predictions for each.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ml.db.config import connect, load_db_config
from ml.db.repositories import fetch_all
from ml.scheduling_v3.placement_direct import DirectPlacementModel, direct_features


def _extract(s: str, before: str, after: str) -> str:
    """Extract substring between two delimiters."""
    i = s.find(before)
    if i < 0:
        return ""
    j = s.find(after, i + len(before))
    if j < 0:
        return s[i + len(before):].strip()
    return s[i + len(before):j].strip()


def test_placement_model(
    allocation_task_id: int = 1,
    top_k: int = 5,
    limit: int = 10,
) -> None:
    """Run placement model on teaching tasks and display predictions."""

    print("Loading model...")
    model = DirectPlacementModel.load()
    print(f"  Features: {len(model.features)} | Classes: {len(model.resource_by_label)}")

    print("Loading data from DB...")
    conn = connect(load_db_config())
    try:
        tasks = list(fetch_all(conn,
            """SELECT tt.id, tt.total_hours, tt.required_room_type,
                      c.name AS course_name, c.code AS course_code,
                      c.course_type, c.required_room_type AS course_room_type,
                      t.name AS teacher_name, t.department AS teacher_department
               FROM teaching_task tt
               JOIN allocation_task_teaching_task att ON tt.id = att.teaching_task_id
               JOIN course c ON tt.course_id = c.id
               JOIN teacher t ON tt.primary_teacher_id = t.id
               WHERE att.allocation_task_id = %s
               ORDER BY tt.id
               LIMIT %s""",
            (allocation_task_id, limit),
        ))

        # Also get class_group for each task
        class_map: dict[int, str] = {}
        task_ids = [t["id"] for t in tasks]
        if task_ids:
            placeholders = ",".join(["%s"] * len(task_ids))
            cgs = list(fetch_all(conn,
                f"""SELECT ttcg.teaching_task_id, cg.name, cg.major, cg.department, cg.grade
                   FROM teaching_task_class_group ttcg
                   JOIN class_group cg ON ttcg.class_group_id = cg.id
                   WHERE ttcg.teaching_task_id IN ({placeholders})""",
                tuple(task_ids),
            ))
        for cg in cgs:
            tid = cg["teaching_task_id"]
            class_map[tid] = f"{cg['name']} ({cg['major']} / {cg['grade']})"

    finally:
        conn.close()

    print(f"\nTesting {len(tasks)} tasks (allocation_task_id={allocation_task_id}):\n")

    hit_count = 0
    for i, task in enumerate(tasks, 1):
        tid = task["id"]
        class_info = class_map.get(tid, "?")

        # Build feature dict
        row = {
            "course_name": task.get("course_name", ""),
            "course_code": task.get("course_code", ""),
            "teacher_no": "",  # DB doesn't have this, model handles empty
            "teacher_name": task.get("teacher_name", ""),
            "class_name": class_info.split(" (")[0] if " (" in class_info else class_info,
            "class_major": _extract(class_info, " (", " /"),
            "class_department": "",
            "class_grade": _extract(class_info, " / ", ")"),
            "student_count": "0",
            "total_hours": str(task.get("total_hours", 0)),
            "course_type": task.get("course_type", ""),
            "required_room_type": task.get("required_room_type", ""),
        }

        try:
            preds = model.predict_topk(row, top_k=top_k)
        except Exception as exc:
            print(f"  #{tid:>4} ERROR: {exc}")
            continue

        print(f"── #{tid:>4} ──────────────────────────────────────────────")
        print(f"  Course:  {task['course_name']} ({task['course_code']})")
        print(f"  Teacher: {task['teacher_name']}")
        print(f"  Class:   {class_info}")
        print(f"  Hours:   {task['total_hours']}h | Type: {task['course_type']}")
        print(f"  Top {top_k}:")
        for rank, (resource_key, score) in enumerate(preds, 1):
            parts = resource_key.split("|")
            room = parts[0] if len(parts) > 0 else "?"
            day = parts[1] if len(parts) > 1 else "?"
            period = parts[2] if len(parts) > 2 else "?"
            marker = " ←" if score > 0.5 else ""
            print(f"    {rank}. {room} | 周{day} | 第{period}节  (score={score:.4f}){marker}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test V3 Placement Model on teaching tasks")
    parser.add_argument("--task-id", type=int, default=1, help="Allocation task ID (default: 1)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of predictions per task")
    parser.add_argument("--limit", type=int, default=10, help="Max tasks to test")
    args = parser.parse_args()

    test_placement_model(
        allocation_task_id=args.task_id,
        top_k=args.top_k,
        limit=args.limit,
    )
