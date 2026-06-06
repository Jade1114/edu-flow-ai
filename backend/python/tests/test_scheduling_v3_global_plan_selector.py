from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from python.scheduling_v3.global_plan_selector import (
    _evaluate,
    _repair,
    load_task_plans,
    select_global_plans_jsonl,
)


def _resource(day: int, period: int, room_id: int, score: float = 0.9) -> dict:
    return {
        "rank": 1,
        "slot": {"day_of_week": day, "period_index": period},
        "classroom": {"id": room_id, "name": f"R{room_id}", "type": "普通教室", "capacity": 80},
        "score": score,
    }


def _task_row(task_id: int, teacher_id: int, class_id: int, plans: list[dict], total_sessions: int = 2) -> dict:
    return {
        "allocation_task_id": 1,
        "teaching_task_id": task_id,
        "input": {"course_name": f"课程{task_id}", "teacher_name": f"T{teacher_id}", "class_name": f"C{class_id}"},
        "task": {
            "total_hours": total_sessions * 2,
            "total_sessions": total_sessions,
            "course_type": "理论课",
            "required_room_type": "普通教室",
            "teacher_id": teacher_id,
            "class_group_ids": [class_id],
        },
        "plans": plans,
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


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


class SchedulingV3GlobalPlanSelectorTest(unittest.TestCase):
    def test_plan_expansion_matches_total_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [_task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1, 2])])]
            _write_jsonl(path, rows)

            tasks = load_task_plans(path)

            self.assertEqual(len(tasks), 1)
            option = tasks[0].options[0]
            self.assertEqual(len(option.assignments), 2)
            self.assertEqual(option.hard_static, 0)

    def test_evaluate_detects_teacher_class_and_room_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [
                _task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])], total_sessions=1),
                _task_row(2, 10, 100, [_plan("p2", _resource(1, 1, 1), [1])], total_sessions=1),
            ]
            _write_jsonl(path, rows)
            tasks = load_task_plans(path)

            evaluated = _evaluate((0, 0), tasks)

            self.assertEqual(evaluated.fitness.conflict_summary["teacher"], 1)
            self.assertEqual(evaluated.fitness.conflict_summary["class"], 1)
            self.assertEqual(evaluated.fitness.conflict_summary["room"], 1)
            self.assertEqual(evaluated.fitness.hard_conflicts, 3)

    def test_fitness_key_prioritizes_hard_conflicts_over_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [
                _task_row(
                    1,
                    10,
                    100,
                    [
                        _plan("p1_bad", _resource(1, 1, 1, score=0.99), [1], score=100.0),
                        _plan("p1_ok", _resource(1, 2, 2, score=0.01), [1], score=0.01),
                    ],
                    total_sessions=1,
                ),
                _task_row(2, 11, 101, [_plan("p2", _resource(1, 1, 1), [1])], total_sessions=1),
            ]
            _write_jsonl(path, rows)
            tasks = load_task_plans(path)

            conflicted = _evaluate((0, 0), tasks)
            clean = _evaluate((1, 0), tasks)

            self.assertGreater(conflicted.fitness.hard_conflicts, clean.fitness.hard_conflicts)
            self.assertLess(clean.fitness.key, conflicted.fitness.key)

    def test_repair_switches_conflicting_task_to_clean_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [
                _task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])], total_sessions=1),
                _task_row(
                    2,
                    11,
                    101,
                    [
                        _plan("p2_bad", _resource(1, 1, 1), [1]),
                        _plan("p2_clean", _resource(2, 1, 2), [1]),
                    ],
                    total_sessions=1,
                ),
            ]
            _write_jsonl(path, rows)
            tasks = load_task_plans(path)

            repaired = _repair((0, 0), tasks)

            self.assertEqual(repaired, (0, 1))
            self.assertEqual(_evaluate(repaired, tasks).fitness.hard_conflicts, 0)

    def test_select_global_plans_writes_jsonl_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_plans.jsonl"
            rows = [
                _task_row(1, 10, 100, [_plan("p1", _resource(1, 1, 1), [1])], total_sessions=1),
                _task_row(2, 11, 101, [_plan("p2", _resource(2, 1, 2), [1])], total_sessions=1),
            ]
            _write_jsonl(path, rows)

            summary = select_global_plans_jsonl(
                path,
                scheme_count=1,
                population_size=6,
                generations=3,
                elite_size=2,
                repair_top_k=2,
                seed=7,
            )

            schemes_path = Path(summary["output_path"])
            self.assertTrue(schemes_path.exists())
            scheme = json.loads(schemes_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(scheme["hard_conflicts"], 0)
            self.assertEqual(len(scheme["items"]), 2)
            self.assertEqual(len(scheme["chromosome"]), 2)


if __name__ == "__main__":
    unittest.main()
