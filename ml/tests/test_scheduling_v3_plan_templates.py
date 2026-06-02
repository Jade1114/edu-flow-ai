from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ml.scheduling_v3.plan_templates import generate_task_plans_jsonl


def _candidate_row(task_id: int, total_hours: int, resource: dict, *, allowed_weeks: list[int]) -> dict:
    return {
        "allocation_task_id": 1,
        "teaching_task_id": task_id,
        "task": {
            "total_hours": total_hours,
            "total_sessions": total_hours // 2,
            "course_type": "理论课",
            "required_room_type": "普通教室",
            "teacher_id": task_id + 100,
            "class_group_ids": [task_id + 1000],
        },
        "input": {
            "course_name": f"课程{task_id}",
            "teacher_no": f"T{task_id}",
            "teacher_name": f"教师{task_id}",
            "class_name": f"班级{task_id}",
        },
        "resources": [resource],
        "meta": {"allowed_weeks": allowed_weeks, "top_k": 1},
    }


def _resource(room_id: int = 1, day: int = 1, period: int = 1, score: float = 0.9) -> dict:
    return {
        "rank": 1,
        "slot": {"day_of_week": day, "period_index": period},
        "classroom": {"id": room_id, "name": f"R{room_id}", "type": "普通教室", "capacity": 80},
        "score": score,
        "source": "placement_model",
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


class SchedulingV3PlanTemplatesTest(unittest.TestCase):
    def test_total_sessions_match_segment_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "placement_candidates.jsonl"
            _write_jsonl(path, [_candidate_row(1, 8, _resource(), allowed_weeks=[1, 2, 3, 4, 5, 6])])

            summary = generate_task_plans_jsonl(path, plan_count=1)
            row = json.loads(Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()[0])

            plan = row["plans"][0]
            self.assertEqual(plan["total_sessions"], 4)
            self.assertEqual(sum(len(segment["weeks"]) for segment in plan["segments"]), 4)
            self.assertTrue(plan["valid"])

    def test_short_task_does_not_default_to_front_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "placement_candidates.jsonl"
            _write_jsonl(path, [_candidate_row(1, 8, _resource(), allowed_weeks=[1, 2, 3, 4, 5, 6])])

            summary = generate_task_plans_jsonl(path, plan_count=1)
            row = json.loads(Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()[0])
            weeks = row["plans"][0]["segments"][0]["weeks"]

            self.assertEqual(len(weeks), 4)
            self.assertNotEqual(weeks, [1, 2, 3, 4])
            self.assertEqual(row["plans"][0]["week_strategy"], "resource_aware_low_usage")

    def test_same_resource_tasks_receive_different_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "placement_candidates.jsonl"
            resource = _resource(room_id=1, day=2, period=3)
            _write_jsonl(path, [
                _candidate_row(1, 8, resource, allowed_weeks=[1, 2, 3, 4, 5, 6]),
                _candidate_row(2, 8, resource, allowed_weeks=[1, 2, 3, 4, 5, 6]),
            ])

            summary = generate_task_plans_jsonl(path, plan_count=1)
            rows = [
                json.loads(line)
                for line in Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()
            ]
            first_weeks = rows[0]["plans"][0]["segments"][0]["weeks"]
            second_weeks = rows[1]["plans"][0]["segments"][0]["weeks"]

            self.assertNotEqual(first_weeks, second_weeks)
            self.assertEqual(rows[0]["plans"][0]["segments"][0]["resource_key"], "1|2|3")


if __name__ == "__main__":
    unittest.main()
