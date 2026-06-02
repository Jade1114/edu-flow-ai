from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ml.scheduling_v3 import cp_sat_selector
from ml.scheduling_v3.cp_sat_selector import (
    audit_scheme_items,
    load_cp_sat_task_plans,
    select_cp_sat_global_plans_jsonl,
)


HAS_ORTOOLS = cp_sat_selector.cp_model is not None


def _resource(day: int, period: int, room_id: int, score: float = 0.9) -> dict:
    return {
        "rank": 1,
        "slot": {"day_of_week": day, "period_index": period},
        "classroom": {"id": room_id, "name": f"R{room_id}", "type": "普通教室", "capacity": 80},
        "score": score,
    }


def _plan(plan_id: str, resource: dict, weeks: list[int], score: float = 0.9) -> dict:
    return {
        "plan_id": plan_id,
        "plan_rank": 1,
        "segments": [
            {
                "template_id": "t1",
                "resource_rank": resource["rank"],
                "resource": resource,
                "weeks": weeks,
                "session_count": len(weeks),
            }
        ],
        "total_sessions": len(weeks),
        "total_hours": len(weeks) * 2,
        "score": score,
        "valid": True,
    }


def _task_row(task_id: int, teacher_id: int, class_id: int, plans: list[dict]) -> dict:
    return {
        "allocation_task_id": 1,
        "teaching_task_id": task_id,
        "input": {"course_name": f"课程{task_id}"},
        "task": {
            "total_hours": 2,
            "total_sessions": 1,
            "teacher_id": teacher_id,
            "class_group_ids": [class_id],
        },
        "plans": plans,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


class SchedulingV3CpSatSelectorTest(unittest.TestCase):
    def test_plan_coordinates_are_mapped_to_real_time_slot_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            _write_jsonl(path, [_task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])])])

            tasks = load_cp_sat_task_plans(path, time_slot_id_by_coord={(1, 1, 1): 9001})

            self.assertEqual(tasks[0].options[0].assignments[0]["time_slot_id"], 9001)

    def test_missing_time_slot_mapping_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            _write_jsonl(path, [_task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])])])

            with self.assertRaisesRegex(ValueError, "unavailable time slot"):
                load_cp_sat_task_plans(path, time_slot_id_by_coord={(1, 1, 2): 9002})

    @unittest.skipUnless(HAS_ORTOOLS, "ortools is not installed")
    def test_cp_sat_selects_zero_conflict_combination(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [
                _task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])]),
                _task_row(
                    2,
                    10,
                    101,
                    [
                        _plan("p2_bad_teacher", _resource(1, 1, 2), [1], score=1.0),
                        _plan("p2_clean", _resource(1, 2, 2), [1], score=0.1),
                    ],
                ),
                _task_row(
                    3,
                    11,
                    100,
                    [
                        _plan("p3_bad_class_room", _resource(1, 1, 1), [1], score=1.0),
                        _plan("p3_clean", _resource(2, 1, 3), [1], score=0.1),
                    ],
                ),
            ]
            _write_jsonl(path, rows)

            summary = select_cp_sat_global_plans_jsonl(
                path,
                time_slot_id_by_coord={(1, 1, 1): 9001, (1, 1, 2): 9002, (1, 2, 1): 9003},
                scheme_count=1,
                time_limit_seconds=5,
            )

            scheme = json.loads(Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(scheme["hard_conflicts"], 0)
            self.assertEqual(audit_scheme_items(scheme["items"])["teacher"], 0)
            self.assertEqual(audit_scheme_items(scheme["items"])["class"], 0)
            self.assertEqual(audit_scheme_items(scheme["items"])["room"], 0)

    @unittest.skipUnless(HAS_ORTOOLS, "ortools is not installed")
    def test_scheme_count_three_uses_diversity_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = []
            coords = {}
            for task_id in range(1, 4):
                plans = []
                for plan_no in range(1, 4):
                    coords[(1, task_id, plan_no)] = 8000 + task_id * 10 + plan_no
                    plans.append(_plan(f"t{task_id}_p{plan_no}", _resource(task_id, plan_no, task_id * 10 + plan_no), [1]))
                rows.append(_task_row(task_id, 100 + task_id, 200 + task_id, plans))
            _write_jsonl(path, rows)

            summary = select_cp_sat_global_plans_jsonl(
                path,
                time_slot_id_by_coord=coords,
                scheme_count=3,
                diversity_threshold=1,
                time_limit_seconds=5,
            )
            lines = Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()
            chromosomes = {tuple(json.loads(line)["chromosome"]) for line in lines}

            self.assertEqual(summary["scheme_count"], 3)
            self.assertEqual(len(chromosomes), 3)

    def test_atomic_fallback_prefers_middle_semester_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            plans = [
                _plan(f"p{week}", _resource(1, 1, week), [week], score=0.9)
                for week in range(1, 19)
            ]
            _write_jsonl(path, [_task_row(1, 10, 100, plans)])
            mapping = {(week, 1, 1): 9000 + week for week in range(1, 19)}
            tasks = load_cp_sat_task_plans(path, time_slot_id_by_coord=mapping)

            scheme, summary = cp_sat_selector._atomic_session_fallback_scheme(1, tasks)

            self.assertIsNotNone(scheme)
            self.assertEqual(summary["failed_task_count"], 0)
            self.assertIn(scheme["items"][0]["week_number"], {8, 9})


if __name__ == "__main__":
    unittest.main()
