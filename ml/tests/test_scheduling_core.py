from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from ml.ga_config import resolve_ga_params
from ml.scheduling.enumerator import enumerate_template_sets
from ml.scheduling.ga import penalty_count, init_population
from ml.scheduling.pipeline import _to_rows, generate_scheme
from ml.scheduling.assignment_scorer import AssignmentScorer
from ml.scheduling.teacher_profiles import load_teacher_profiles_jsonl
from ml.scheduling.types import AllocationTask, Template, TemplateAssignment, TemplateSet, TaskGene, weeks_to_mask


def _task(
    task_id: int,
    teacher_id: int,
    class_group_ids: tuple[int, ...],
    room_ids: list[int],
) -> AllocationTask:
    template_set = TemplateSet(
        templates=[Template(week_mask=weeks_to_mask([1, 2]), weeks_list=[1, 2])],
        penalty=0,
    )
    return AllocationTask(
        task_id=task_id,
        teacher_id=teacher_id,
        class_group_id=class_group_ids[0],
        student_count=30,
        total_lessons=2,
        available_week_mask=weeks_to_mask([1, 2]),
        candidate_slot_ids=[0],
        candidate_room_ids=room_ids,
        template_sets=[template_set],
        class_group_ids=class_group_ids,
    )


class SchedulingCoreTest(unittest.TestCase):
    def test_ga_profile_fast_resolves_smaller_validation_params(self) -> None:
        with patch.dict("os.environ", {"ML_GA_PROFILE": "fast"}, clear=False):
            params = resolve_ga_params()

        self.assertEqual(params["profile"], "fast")
        self.assertLess(params["population_size"], 60)
        self.assertLess(params["generations"], 60)

    def test_ga_env_overrides_profile_params_with_bounds(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ML_GA_PROFILE": "fast",
                "ML_GA_POPULATION_SIZE": "8",
                "ML_GA_GENERATIONS": "2",
                "ML_GA_MUTATION_RATE": "2.5",
            },
            clear=False,
        ):
            params = resolve_ga_params()

        self.assertEqual(params["population_size"], 8)
        self.assertEqual(params["generations"], 2)
        self.assertEqual(params["mutation_rate"], 1.0)

    def test_template_enumerator_includes_non_prefix_week_patterns(self) -> None:
        template_sets = enumerate_template_sets(8, list(range(1, 19)))

        self.assertTrue(template_sets)
        week_patterns = {
            tuple(template.weeks_list)
            for template_set in template_sets
            for template in template_set.templates
        }
        self.assertIn((6, 7, 8, 9, 10, 11, 12, 13), week_patterns)
        self.assertNotEqual(template_sets[0].templates[0].weeks_list, list(range(1, 9)))

    def test_template_enumerator_reuses_cached_shapes(self) -> None:
        first = enumerate_template_sets(24, list(range(1, 19)))
        second = enumerate_template_sets(24, list(range(1, 19)))

        self.assertEqual(first, second)

    def test_template_enumerator_covers_all_available_weeks_when_lessons_exceed_weeks(self) -> None:
        template_sets = enumerate_template_sets(24, list(range(1, 19)))

        first = template_sets[0]
        active_weeks = {
            week
            for template in first.templates
            for week in template.weeks_list
        }

        self.assertEqual(active_weeks, set(range(1, 19)))

    def test_init_allows_parallel_courses_when_hard_resources_differ(self) -> None:
        tasks = [
            _task(1, teacher_id=1, class_group_ids=(101,), room_ids=[1]),
            _task(2, teacher_id=2, class_group_ids=(102,), room_ids=[2]),
        ]

        population = init_population(tasks, pop_size=1, rng=random.Random(7), init_candidate_top_n=5)

        self.assertEqual({gene.task_id for gene in population[0]}, {1, 2})
        pc = penalty_count(population[0], tasks)
        self.assertEqual(pc["missing_task_count"], 0)
        self.assertEqual(pc["hard_conflicts"], 0)

    def test_fitness_penalizes_missing_task(self) -> None:
        tasks = [
            _task(1, teacher_id=1, class_group_ids=(101,), room_ids=[1]),
            _task(2, teacher_id=2, class_group_ids=(102,), room_ids=[2]),
        ]
        chromosome = [
            TaskGene(
                task_id=1,
                template_set_id=0,
                assignments=[TemplateAssignment(template_id=0, slot_id=0, classroom_id=1)],
            )
        ]

        pc = penalty_count(chromosome, tasks)

        self.assertEqual(pc["missing_task_count"], 1)
        self.assertGreaterEqual(pc["hard_conflicts"], 1)

    def test_fitness_detects_any_overlapping_class_group_in_joint_class(self) -> None:
        tasks = [
            _task(1, teacher_id=1, class_group_ids=(101, 102), room_ids=[1]),
            _task(2, teacher_id=2, class_group_ids=(102, 103), room_ids=[2]),
        ]
        chromosome = [
            TaskGene(1, 0, [TemplateAssignment(0, 0, 1)]),
            TaskGene(2, 0, [TemplateAssignment(0, 0, 2)]),
        ]

        pc = penalty_count(chromosome, tasks)

        self.assertGreaterEqual(pc["hard_conflicts"], 1)

    def test_to_rows_uses_db_time_slot_id_mapping(self) -> None:
        task = _task(1, teacher_id=1, class_group_ids=(101,), room_ids=[1])
        chromosome = [
            TaskGene(1, 0, [TemplateAssignment(template_id=0, slot_id=0, classroom_id=1)])
        ]
        time_slot_id_by_coord = {
            (1, 1, 1): 9001,
            (2, 1, 1): 9002,
        }

        rows = _to_rows(chromosome, [task], [{"teaching_task_id": 1}], time_slot_id_by_coord)

        self.assertEqual([row["time_slot_id"] for row in rows], [9001, 9002])

    def test_to_rows_outputs_teacher_profile_penalty_explanation(self) -> None:
        task = _task(1, teacher_id=1, class_group_ids=(101,), room_ids=[1])
        task = task._replace(teacher_profile={
            "soft_avoid": [{"weekday": 1, "periods": [1], "penalty": 60, "reason": "周一第一节尽量不排"}],
            "hard_unavailable": set(),
        })
        chromosome = [TaskGene(1, 0, [TemplateAssignment(template_id=0, slot_id=0, classroom_id=1)])]
        time_slot_id_by_coord = {(1, 1, 1): 9001, (2, 1, 1): 9002}

        rows = _to_rows(chromosome, [task], [{"teaching_task_id": 1}], time_slot_id_by_coord)

        self.assertEqual(rows[0]["teacher_profile_penalty"], 60)
        self.assertIn("周一第一节", rows[0]["teacher_profile_penalty_explanation"])

    def test_generate_scheme_filters_teacher_hard_unavailable_slot(self) -> None:
        tasks_data = [{
            "teaching_task_id": 1,
            "teacher_id": 1,
            "total_hours": 2,
            "total_student_count": 20,
            "class_group_ids": "101",
            "teacher_name": "T1",
        }]
        classrooms = [{"id": 1, "capacity": 40, "classroom_type": "", "building": "A"}]
        time_slots = [
            {"id": 11, "week_number": 1, "day_of_week": 1, "period_index": 1},
            {"id": 12, "week_number": 1, "day_of_week": 2, "period_index": 1},
        ]
        teacher_profiles = {
            1: {"profile": {"hard_unavailable": [{"weekday": 1, "period": 1}]}}
        }

        rows, metrics = generate_scheme(
            tasks_data,
            classrooms,
            time_slots,
            teacher_profiles,
            rng=random.Random(3),
            population_size=3,
            generations=1,
        )

        self.assertEqual(rows[0]["day_of_week"], 2)
        self.assertEqual(rows[0]["time_slot_id"], 12)
        audit = metrics["teacher_profile_audit"]
        self.assertEqual(audit["tasks_with_hard_unavailable"], 1)
        self.assertEqual(audit["candidate_slot_removed_by_hard_filter"], 1)
        self.assertEqual(audit["tasks"][0]["hard_unavailable_slots"], [{"weekday": 1, "period": 1}])

    def test_load_teacher_profiles_jsonl_normalizes_slots(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.jsonl"
            path.write_text(
                '{"teacher_id":1,"profile":{"hard_unavailable":[{"weekday":1,"period":"*"}],"soft_avoid":[{"weekday":2,"periods":[2,9],"penalty":160,"reason":"偏好"}]}}\n',
                encoding="utf-8",
            )

            profiles = load_teacher_profiles_jsonl(path)

        self.assertEqual(profiles[1]["hard_unavailable"], {(1, 1), (1, 2), (1, 3), (1, 4), (1, 5)})
        self.assertEqual(profiles[1]["soft_avoid"][0]["periods"], [2])
        self.assertEqual(profiles[1]["soft_avoid"][0]["penalty"], 100)

    def test_load_teacher_profiles_jsonl_accepts_service_snapshot_shape(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.jsonl"
            path.write_text(
                (
                    '{"teacher_id":1,'
                    '"availability_matrix_json":"[[0,-1,0,0,0,0,0],[0,0,0,0,0,0,0]]",'
                    '"profile":{"avoidFirstPeriod":true,"avoidLastPeriod":true,'
                    '"preferredMaxWeeklyHours":6,"preferCompactSchedule":true}}\n'
                ),
                encoding="utf-8",
            )

            profiles = load_teacher_profiles_jsonl(path)

        self.assertEqual(profiles[1]["hard_unavailable"], {(2, 1)})
        self.assertEqual(profiles[1]["avoid_periods"], [1, 5])
        self.assertEqual(profiles[1]["max_weekly_lessons"], 6)
        self.assertTrue(profiles[1]["prefer_compact_schedule"])

    def test_assignment_scorer_builds_teacher_profile_features(self) -> None:
        from pathlib import Path

        task = _task(1, teacher_id=1, class_group_ids=(101,), room_ids=[1])
        task = task._replace(teacher_profile={
            "hard_unavailable": {(1, 1)},
            "soft_avoid": [{"weekday": 1, "periods": [1], "penalty": 60, "reason": "避开"}],
            "preferred_weekdays": [2],
            "avoid_periods": [1, 5],
            "prefer_compact_schedule": True,
            "max_weekly_lessons": 6,
        })
        scorer = AssignmentScorer(
            task_data_by_id={1: {"course_type": "专业课", "total_hours": 2}},
            classroom_by_id={1: {"capacity": 40, "classroom_type": "普通教室", "building": "A"}},
            model_path=Path("/tmp/nonexistent-model.txt"),
            feature_schema_path=Path("/tmp/nonexistent-schema.json"),
        )

        row = scorer._build_feature_row(task, week_number=1, slot_id=0, classroom_id=1)

        self.assertEqual(row["teacher_matrix_value"], -1)
        self.assertEqual(row["teacher_avoid_first_period"], 1)
        self.assertEqual(row["teacher_avoid_last_period"], 1)
        self.assertEqual(row["teacher_prefer_compact_schedule"], 1)
        self.assertEqual(row["teacher_preferred_weekday_match"], 0)
        self.assertEqual(row["teacher_avoid_slot_match"], 1)
        self.assertEqual(row["teacher_preferred_max_weekly_hours"], 6)


if __name__ == "__main__":
    unittest.main()
