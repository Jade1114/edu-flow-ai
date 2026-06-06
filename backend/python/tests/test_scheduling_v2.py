from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from python.ga_config import resolve_ga_params
from python.scheduling.scoring import build_scoring_config
from python.scheduling_v2.candidate_pool import (
    _candidate_combinations,
    _expand_task_candidates_local,
    _rank_rooms,
    _rank_slot_options,
    _select_covered_slot_options,
    build_candidate_pool,
)
from python.scheduling_v2.data_loader import is_excluded_course
from python.scheduling_v2.fitness import evaluate
from python.scheduling_v2.ga_solver import (
    _build_candidate_index,
    _build_chromosome_state,
    _directed_mutate,
    _local_replacement_candidates,
    _global_greedy_chromosome,
    _repair,
    _replace_candidate_state,
    solve,
)
from python.scheduling_v2.models import (
    AssignmentRef,
    ScheduleContext,
    SchedTask,
    TaskCandidate,
    TimeSlotRef,
)
from python.scheduling_v2.placement_ranker import _features_for_candidate
from python.scheduling_v2.pipeline import validate_hard_feasibility
from python.scheduling_v2.slot_ranker import rank_slots
from python.training.build_slot_ranker_training_data import _period_start_to_index


def _assignment(task_id: int, teacher_id: int, class_id: int, room_id: int, slot_id: int, week: int, day: int, period: int):
    return AssignmentRef(
        teaching_task_id=task_id,
        teacher_id=teacher_id,
        class_group_ids=(class_id,),
        classroom_id=room_id,
        time_slot_id=slot_id,
        week_number=week,
        day_of_week=day,
        period_index=period,
        room_rank_score=0.8,
    )


def _candidate(task_id: int, index: int, assignments: tuple[AssignmentRef, ...], score: float = 1.0):
    return TaskCandidate(
        teaching_task_id=task_id,
        candidate_index=index,
        assignments=assignments,
        template_signature=f"candidate-{index}",
        score=score,
        room_rank_score=score,
        teacher_profile_penalty=0.0,
    )


def _candidate_with_template(task_id: int, index: int, assignments: tuple[AssignmentRef, ...], template: str, score: float = 1.0):
    return TaskCandidate(
        teaching_task_id=task_id,
        candidate_index=index,
        assignments=assignments,
        template_signature=template,
        score=score,
        room_rank_score=score,
        teacher_profile_penalty=0.0,
    )


class SchedulingV2Test(unittest.TestCase):
    def setUp(self):
        self.context = ScheduleContext(
            task_id=1,
            task_name="demo",
            raw_config={"scheme_count": 2},
            scoring_config=build_scoring_config(None),
            tasks=(
                SchedTask(1, 10, "T1", 4, 2, 30, "", (100,), {"teaching_task_id": 1}),
                SchedTask(2, 11, "T2", 4, 2, 30, "", (101,), {"teaching_task_id": 2}),
            ),
            classrooms=(),
            time_slots=(),
            slot_by_coord={
                (1, 1, 1): TimeSlotRef(1, 1, 1, 1),
                (2, 1, 1): TimeSlotRef(2, 2, 1, 1),
                (1, 1, 2): TimeSlotRef(3, 1, 1, 2),
                (2, 1, 2): TimeSlotRef(4, 2, 1, 2),
            },
            allowed_time_slot_ids=frozenset({1, 2, 3, 4}),
        )

    def test_fitness_detects_teacher_conflict_and_hour_mismatch(self):
        pools = [
            [_candidate(1, 0, (_assignment(1, 10, 100, 1, 1, 1, 1, 1),), 1.0)],
            [_candidate(2, 0, (_assignment(2, 10, 101, 2, 1, 1, 1, 1),), 1.0)],
        ]

        result = evaluate((0, 0), self.context, pools)

        self.assertGreater(result.hard_conflicts, 0)
        self.assertEqual(result.conflict_summary["TEACHER_TIME"], 1)
        self.assertEqual(result.conflict_summary["TEACHING_TASK_HOURS"], 2)

    def test_placement_ranker_reads_sched_task_raw_fields(self):
        task = SchedTask(
            1,
            10,
            "张老师",
            4,
            2,
            45,
            "普通教室",
            (100,),
            {
                "course_code": "CS101",
                "course_name": "程序设计",
                "course_type": "理论课",
                "class_group_names": "2024级软件2班",
                "class_group_majors": "软件工程",
                "teacher_department": "计算机学院",
            },
        )

        features = _features_for_candidate(
            task,
            {
                "room_name": "一教101",
                "room_type": "普通教室",
                "room_capacity": 60,
                "day": 1,
                "period": 2,
            },
            {},
        )

        self.assertGreater(features["course_code_code"], 0)
        self.assertGreater(features["class_group_name_code"], 0)
        self.assertEqual(features["class_grade"], 2024)
        self.assertEqual(features["class_no"], 2)
        self.assertEqual(features["required_type_match"], 1.0)

    def test_solver_returns_distinct_feasible_schemes(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
                _candidate(1, 1, (
                    _assignment(1, 10, 100, 1, 3, 1, 1, 2),
                    _assignment(1, 10, 100, 1, 4, 2, 1, 2),
                ), 0.9),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 1.0),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 2, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 2, 2, 2, 1, 1),
                ), 0.9),
            ],
        ]

        schemes = solve(
            self.context,
            pools,
            scheme_count=2,
            population_size=8,
            generations=8,
            elite_size=2,
            tournament_size=2,
            mutation_rate=0.5,
            rng=random.Random(1),
        )

        self.assertEqual(len(schemes), 2)
        self.assertTrue(all(scheme.fitness.hard_conflicts == 0 for scheme in schemes))
        self.assertEqual(len({scheme.chromosome for scheme in schemes}), 2)

    def test_solver_can_repair_conflict_with_deeper_candidate(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 11, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 1, 2, 2, 1, 1),
                ), 1.0),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 1, 2, 2, 1, 1),
                ), 0.95),
                _candidate(2, 2, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 0.7),
            ],
        ]

        schemes = solve(
            self.context,
            pools,
            scheme_count=1,
            population_size=4,
            generations=4,
            elite_size=1,
            tournament_size=2,
            mutation_rate=0.0,
            rng=random.Random(2),
        )

        self.assertEqual(len(schemes), 1)
        self.assertEqual(schemes[0].fitness.hard_conflicts, 0)
        self.assertEqual(schemes[0].chromosome[1], 2)

    def test_incremental_state_matches_full_evaluate(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 10, 101, 2, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 2, 2, 2, 1, 1),
                ), 0.8),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)

        state = _build_chromosome_state((0, 0), candidate_index)
        full = evaluate((0, 0), self.context, pools)

        self.assertEqual(state.hard_conflicts, full.hard_conflicts)
        self.assertAlmostEqual(state.quality_score, full.quality_score)

    def test_incremental_replace_matches_full_evaluate(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 10, 101, 2, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 2, 2, 2, 1, 1),
                ), 0.8),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 0.7),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)
        state = _build_chromosome_state((0, 0), candidate_index)

        replaced = _replace_candidate_state(state, 1, 1, candidate_index)
        full = evaluate((0, 1), self.context, pools)

        self.assertEqual(replaced.chromosome, (0, 1))
        self.assertEqual(replaced.hard_conflicts, full.hard_conflicts)
        self.assertAlmostEqual(replaced.quality_score, full.quality_score)

    def test_repair_budget_zero_keeps_child_unchanged(self):
        pools = [
            [_candidate(1, 0, (_assignment(1, 10, 100, 1, 1, 1, 1, 1),), 1.0)],
            [_candidate(2, 0, (_assignment(2, 10, 101, 2, 1, 1, 1, 1),), 1.0)],
        ]
        candidate_index = _build_candidate_index(self.context, pools)

        repaired, improved, stats = _repair(
            (0, 0),
            pools,
            candidate_index,
            random.Random(1),
            max_tasks=0,
            candidate_limit=12,
        )

        self.assertEqual(repaired, (0, 0))
        self.assertFalse(improved)
        self.assertEqual(stats.trials, 0)

    def test_incremental_repair_never_worsens_full_evaluate(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 10, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 1, 2, 2, 1, 1),
                ), 1.0),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 1, 2, 2, 1, 1),
                ), 0.9),
                _candidate(2, 2, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 0.7),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)
        before = evaluate((0, 0), self.context, pools)

        repaired, _improved, stats = _repair(
            (0, 0),
            pools,
            candidate_index,
            random.Random(1),
            max_tasks=2,
            candidate_limit=3,
        )
        after = evaluate(repaired, self.context, pools)

        self.assertEqual(len(repaired), 2)
        self.assertTrue(all(0 <= gene < len(pool) for gene, pool in zip(repaired, pools)))
        self.assertLessEqual(after.hard_conflicts, before.hard_conflicts)
        self.assertGreater(stats.trials, 0)

    def test_global_greedy_init_does_not_worsen_baseline(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 10, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 1, 2, 2, 1, 1),
                ), 1.0),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 0.7),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)

        baseline = evaluate((0, 0), self.context, pools)
        greedy = _global_greedy_chromosome(
            pools,
            candidate_index,
            random.Random(1),
            scan_limit=4,
            randomize_order=False,
        )
        greedy_result = evaluate(greedy, self.context, pools)

        self.assertLessEqual(greedy_result.hard_conflicts, baseline.hard_conflicts)

    def test_randomized_global_greedy_keeps_gene_bounds(self):
        pools = [
            [_candidate(1, 0, (_assignment(1, 10, 100, 1, 1, 1, 1, 1),), 1.0)],
            [
                _candidate(2, 0, (_assignment(2, 11, 101, 1, 1, 1, 1, 1),), 1.0),
                _candidate(2, 1, (_assignment(2, 11, 101, 2, 3, 1, 1, 2),), 0.8),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)

        chromosome = _global_greedy_chromosome(
            pools,
            candidate_index,
            random.Random(3),
            scan_limit=2,
            randomize_order=True,
        )

        self.assertEqual(len(chromosome), len(pools))
        self.assertTrue(all(0 <= gene < len(pool) for gene, pool in zip(chromosome, pools)))

    def test_directed_mutation_does_not_increase_full_conflicts(self):
        pools = [
            [
                _candidate(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), 1.0),
            ],
            [
                _candidate(2, 0, (
                    _assignment(2, 10, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 1, 2, 2, 1, 1),
                ), 1.0),
                _candidate(2, 1, (
                    _assignment(2, 11, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 11, 101, 2, 4, 2, 1, 2),
                ), 0.7),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)
        before = evaluate((0, 0), self.context, pools)

        mutated, stats = _directed_mutate(
            (0, 0),
            pools,
            candidate_index,
            mutation_rate=1.0,
            rng=random.Random(4),
            scan_limit=2,
        )
        after = evaluate(mutated, self.context, pools)

        self.assertLessEqual(after.hard_conflicts, before.hard_conflicts)
        self.assertTrue(all(0 <= gene < len(pool) for gene, pool in zip(mutated, pools)))
        self.assertGreaterEqual(stats.directed_applied + stats.random_fallback, 0)

    def test_local_replacement_groups_slot_and_room_alternatives(self):
        pools = [[
            _candidate_with_template(1, 0, (
                _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                _assignment(1, 10, 100, 1, 2, 2, 1, 1),
            ), "template-a", 1.0),
            _candidate_with_template(1, 1, (
                _assignment(1, 10, 100, 2, 1, 1, 1, 1),
                _assignment(1, 10, 100, 2, 2, 2, 1, 1),
            ), "template-a", 0.9),
            _candidate_with_template(1, 2, (
                _assignment(1, 10, 100, 1, 3, 1, 1, 2),
                _assignment(1, 10, 100, 1, 4, 2, 1, 2),
            ), "template-a", 0.8),
        ]]
        candidate_index = _build_candidate_index(self.context, pools)

        room_choices = _local_replacement_candidates(candidate_index, 0, 0, {"room": 1}, limit=4)
        slot_choices = _local_replacement_candidates(candidate_index, 0, 0, {"teacher": 1}, limit=4)

        self.assertEqual(room_choices[0], (1, "room_only"))
        self.assertEqual(slot_choices[0], (2, "teacher_slot"))

    def test_local_repair_prefers_room_only_for_classroom_conflict(self):
        pools = [
            [
                _candidate_with_template(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), "template-a", 1.0),
            ],
            [
                _candidate_with_template(2, 0, (
                    _assignment(2, 11, 101, 1, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 1, 2, 2, 1, 1),
                ), "template-a", 1.0),
                _candidate_with_template(2, 1, (
                    _assignment(2, 11, 101, 2, 1, 1, 1, 1),
                    _assignment(2, 11, 101, 2, 2, 2, 1, 1),
                ), "template-a", 0.9),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)
        before = evaluate((0, 0), self.context, pools)

        repaired, improved, stats = _repair(
            (0, 0),
            pools,
            candidate_index,
            random.Random(1),
            max_tasks=2,
            candidate_limit=2,
            local_enabled=True,
            local_candidate_limit=2,
        )
        after = evaluate(repaired, self.context, pools)

        self.assertTrue(improved)
        self.assertEqual(repaired, (0, 1))
        self.assertLessEqual(after.hard_conflicts, before.hard_conflicts)
        self.assertEqual(stats.local_room_only, 1)

    def test_local_repair_prefers_slot_for_teacher_conflict(self):
        pools = [
            [
                _candidate_with_template(1, 0, (
                    _assignment(1, 10, 100, 1, 1, 1, 1, 1),
                    _assignment(1, 10, 100, 1, 2, 2, 1, 1),
                ), "template-a", 1.0),
            ],
            [
                _candidate_with_template(2, 0, (
                    _assignment(2, 10, 101, 2, 1, 1, 1, 1),
                    _assignment(2, 10, 101, 2, 2, 2, 1, 1),
                ), "template-a", 1.0),
                _candidate_with_template(2, 1, (
                    _assignment(2, 10, 101, 2, 3, 1, 1, 2),
                    _assignment(2, 10, 101, 2, 4, 2, 1, 2),
                ), "template-a", 0.9),
            ],
        ]
        candidate_index = _build_candidate_index(self.context, pools)
        before = evaluate((0, 0), self.context, pools)

        repaired, improved, stats = _repair(
            (0, 0),
            pools,
            candidate_index,
            random.Random(1),
            max_tasks=2,
            candidate_limit=2,
            local_enabled=True,
            local_candidate_limit=2,
        )
        after = evaluate(repaired, self.context, pools)

        self.assertTrue(improved)
        self.assertEqual(repaired, (0, 1))
        self.assertLessEqual(after.hard_conflicts, before.hard_conflicts)
        self.assertEqual(stats.local_teacher_slot, 1)

    def test_candidate_combinations_keep_slot_diversity(self):
        repeated_room_options = [
            (2, room_id, 1.0, 0.0, "")
            for room_id in range(100, 108)
        ] + [
            (slot_id, 100, 0.9, 0.0, "")
            for slot_id in (7, 12, 17)
        ]
        slot_options = [repeated_room_options for _ in range(4)]

        combos = _candidate_combinations(slot_options, limit=10)

        self.assertTrue(combos)
        self.assertTrue(all(len({value[0] for value in combo}) == 4 for combo in combos))

    def test_slot_option_selection_preserves_day_and_period_coverage(self):
        options = []
        for day in range(1, 6):
            for period in range(1, 5):
                slot_id = (day - 1) * 5 + (period - 1)
                score = 10.0 if day == 1 else 1.0
                options.append((score, slot_id, 100 + period, score, 0.0, ""))
        options.sort(key=lambda item: (-item[0], item[1], item[2]))

        selected = _select_covered_slot_options(options, limit=10, rotation_key=3)
        selected_days = {option[1] // 5 + 1 for option in selected}
        selected_periods = {option[1] % 5 + 1 for option in selected}

        self.assertGreaterEqual(len(selected_days), 3)
        self.assertEqual(selected_periods, {1, 2, 3, 4})

    def test_slot_ranker_rule_fallback(self):
        task = self.context.tasks[0]
        with patch("ml.scheduling_v2.slot_ranker._lazy_load", return_value=(None, [])):
            ranked = rank_slots(task, [(1, 3), (1, 1), (2, 2)], top_n=2)

        self.assertEqual(ranked[0][:2], (1, 1))
        self.assertEqual(len(ranked), 2)

    def test_period_start_maps_to_period_index(self):
        self.assertEqual(_period_start_to_index(1), 1)
        self.assertEqual(_period_start_to_index(3), 2)
        self.assertEqual(_period_start_to_index(5), 3)
        self.assertEqual(_period_start_to_index(None), 0)

    def test_rank_slot_options_keeps_context_time_slot_mapping(self):
        template = type("Template", (), {"weeks_list": [1]})()
        task = self.context.tasks[0]
        rooms = [{"id": 1, "_rank_score": 1.0}]
        context = ScheduleContext(
            task_id=self.context.task_id,
            task_name=self.context.task_name,
            raw_config=self.context.raw_config,
            scoring_config=self.context.scoring_config,
            tasks=self.context.tasks,
            classrooms=self.context.classrooms,
            time_slots=(
                {"id": 1, "week_number": 1, "day_of_week": 1, "period_index": 1},
                {"id": 3, "week_number": 1, "day_of_week": 1, "period_index": 2},
            ),
            slot_by_coord=self.context.slot_by_coord,
            allowed_time_slot_ids=self.context.allowed_time_slot_ids,
        )

        with patch("ml.scheduling_v2.candidate_pool.rank_slots", return_value=[(1, 1, 1.0), (1, 2, 0.5)]):
            options = _rank_slot_options(task, template, rooms, context, limit=2)

        self.assertTrue(options)
        self.assertTrue(all(option[0] in {0, 1} for option in options))

    def test_local_candidate_expansion_outputs_valid_candidates(self):
        time_slots = tuple(
            {
                "id": index + 1,
                "week_number": week,
                "day_of_week": day,
                "period_index": period,
                "label": f"{week}-{day}-{period}",
            }
            for index, (week, day, period) in enumerate(
                (week, day, period)
                for week in range(1, 3)
                for day in range(1, 3)
                for period in range(1, 3)
            )
        )
        slot_by_coord = {
            (int(slot["week_number"]), int(slot["day_of_week"]), int(slot["period_index"])): TimeSlotRef(
                int(slot["id"]),
                int(slot["week_number"]),
                int(slot["day_of_week"]),
                int(slot["period_index"]),
            )
            for slot in time_slots
        }
        task = SchedTask(101, 10, "T1", 4, 2, 30, "普通教室", (100,), {"teaching_task_id": 101})
        context = ScheduleContext(
            task_id=1,
            task_name="expand",
            raw_config=None,
            scoring_config=build_scoring_config(None),
            tasks=(task,),
            classrooms=(
                {"id": 1, "name": "0101", "building": "01", "capacity": 80, "classroom_type": "普通教室"},
                {"id": 2, "name": "0102", "building": "01", "capacity": 70, "classroom_type": "普通教室"},
            ),
            time_slots=time_slots,
            slot_by_coord=slot_by_coord,
            allowed_time_slot_ids=frozenset(slot.id for slot in slot_by_coord.values()),
        )
        pool = [_candidate_with_template(101, 0, (
            _assignment(101, 10, 100, 1, 1, 1, 1, 1),
            _assignment(101, 10, 100, 1, 5, 2, 1, 1),
        ), "template-a", 1.0)]

        expanded, stats = _expand_task_candidates_local(
            task,
            context,
            pool,
            day_periods=[(1, 1), (1, 2), (2, 1), (2, 2)],
            slot_limit=4,
            room_limit=2,
            max_added=4,
        )

        self.assertGreater(stats["added"], 0)
        self.assertTrue(all(len(candidate.assignments) == task.total_lessons for candidate in expanded))
        self.assertTrue(all(
            assignment.time_slot_id in context.allowed_time_slot_ids
            for candidate in expanded
            for assignment in candidate.assignments
        ))

    def test_room_ranker_uses_bound_room_type(self):
        classrooms = tuple(
            {"id": room_id, "capacity": 80, "classroom_type": "机房" if room_id >= 10 else "普通教室"}
            for room_id in range(1, 16)
        )
        task = SchedTask(
            teaching_task_id=23,
            teacher_id=10,
            teacher_name="T1",
            total_hours=4,
            total_lessons=2,
            total_student_count=40,
            required_room_type="",
            class_group_ids=(100,),
            raw={"teaching_task_id": 23, "bound_classroom_id": 12, "bound_classroom_type": "机房"},
        )

        rooms = _rank_rooms(task, classrooms)[:5]

        self.assertEqual(rooms[0]["id"], 12)
        self.assertTrue(all(room["classroom_type"] == "机房" for room in rooms))

    def test_parallel_candidate_pool_preserves_task_order(self):
        time_slots = tuple(
            {
                "id": index + 1,
                "week_number": 1,
                "day_of_week": day,
                "period_index": period,
                "label": f"{day}-{period}",
            }
            for index, (day, period) in enumerate((day, period) for day in range(1, 3) for period in range(1, 3))
        )
        slot_by_coord = {
            (int(slot["week_number"]), int(slot["day_of_week"]), int(slot["period_index"])): TimeSlotRef(
                int(slot["id"]),
                int(slot["week_number"]),
                int(slot["day_of_week"]),
                int(slot["period_index"]),
            )
            for slot in time_slots
        }
        context = ScheduleContext(
            task_id=1,
            task_name="parallel",
            raw_config=None,
            scoring_config=build_scoring_config(None),
            tasks=(
                SchedTask(101, 10, "T1", 2, 1, 30, "普通教室", (100,), {"teaching_task_id": 101}),
                SchedTask(102, 11, "T2", 2, 1, 35, "普通教室", (101,), {"teaching_task_id": 102}),
            ),
            classrooms=(
                {"id": 1, "name": "0101", "building": "01", "capacity": 80, "classroom_type": "普通教室"},
                {"id": 2, "name": "0102", "building": "01", "capacity": 70, "classroom_type": "普通教室"},
            ),
            time_slots=time_slots,
            slot_by_coord=slot_by_coord,
            allowed_time_slot_ids=frozenset(slot.id for slot in slot_by_coord.values()),
        )

        serial = build_candidate_pool(
            context,
            pool_size_per_task=20,
            room_top_n=2,
            template_top_n=2,
            slot_top_n=4,
            candidate_workers=1,
        )
        parallel = build_candidate_pool(
            context,
            pool_size_per_task=20,
            room_top_n=2,
            template_top_n=2,
            slot_top_n=4,
            candidate_workers=2,
        )

        self.assertEqual(len(serial), len(parallel))
        self.assertEqual([pool[0].teaching_task_id for pool in serial], [101, 102])
        self.assertEqual([pool[0].teaching_task_id for pool in parallel], [101, 102])
        self.assertEqual([len(pool) for pool in serial], [len(pool) for pool in parallel])

    def test_candidate_workers_env_config(self):
        with patch.dict("os.environ", {"ML_CANDIDATE_WORKERS": "1"}, clear=True):
            self.assertEqual(resolve_ga_params()["candidate_workers"], 1)
        with patch.dict("os.environ", {"ML_CANDIDATE_WORKERS": "99"}, clear=True):
            self.assertEqual(resolve_ga_params()["candidate_workers"], 16)
        with patch.dict("os.environ", {"ML_CANDIDATE_WORKERS": "bad"}, clear=True):
            self.assertGreaterEqual(resolve_ga_params()["candidate_workers"], 1)
        with patch.dict("os.environ", {}, clear=True), patch("os.cpu_count", return_value=12):
            self.assertEqual(resolve_ga_params()["candidate_workers"], 6)

    def test_ga_scan_limit_env_config(self):
        with patch.dict("os.environ", {
            "ML_GA_GREEDY_INIT_SCAN_LIMIT": "25",
            "ML_GA_GREEDY_INIT_VARIANTS": "9",
            "ML_GA_DIRECTED_MUTATION_SCAN_LIMIT": "35",
            "ML_GA_LOCAL_REPAIR_ENABLED": "false",
            "ML_GA_LOCAL_REPAIR_CANDIDATE_LIMIT": "7",
            "ML_GA_LOCAL_MUTATION_ENABLED": "true",
            "ML_GA_LOCAL_MUTATION_CANDIDATE_LIMIT": "6",
            "ML_CANDIDATE_LOCAL_EXPAND_ENABLED": "false",
            "ML_CANDIDATE_LOCAL_EXPAND_MAX_ADDED_PER_TASK": "13",
        }, clear=True):
            params = resolve_ga_params()

        self.assertEqual(params["greedy_init_scan_limit"], 25)
        self.assertEqual(params["greedy_init_variants"], 9)
        self.assertEqual(params["directed_mutation_scan_limit"], 35)
        self.assertFalse(params["local_repair_enabled"])
        self.assertEqual(params["local_repair_candidate_limit"], 7)
        self.assertTrue(params["local_mutation_enabled"])
        self.assertEqual(params["local_mutation_candidate_limit"], 6)
        self.assertFalse(params["candidate_local_expand_enabled"])
        self.assertEqual(params["candidate_local_expand_max_added_per_task"], 13)

    def test_feasibility_rejects_overloaded_teacher(self):
        context = ScheduleContext(
            task_id=1,
            task_name="overload",
            raw_config=None,
            scoring_config=build_scoring_config(None),
            tasks=(
                SchedTask(1, 10, "T1", 6, 3, 30, "", (100,), {"teaching_task_id": 1}),
                SchedTask(2, 10, "T1", 6, 3, 30, "", (101,), {"teaching_task_id": 2}),
            ),
            classrooms=(),
            time_slots=(),
            slot_by_coord={
                (1, 1, 1): TimeSlotRef(1, 1, 1, 1),
                (1, 1, 2): TimeSlotRef(2, 1, 1, 2),
                (1, 1, 3): TimeSlotRef(3, 1, 1, 3),
                (1, 1, 4): TimeSlotRef(4, 1, 1, 4),
            },
            allowed_time_slot_ids=frozenset({1, 2, 3, 4}),
        )

        with self.assertRaisesRegex(ValueError, "教师超容量"):
            validate_hard_feasibility(context)

    def test_excludes_special_practice_courses(self):
        self.assertTrue(is_excluded_course({
            "course_name": "校企合作综合实训",
            "course_code": "校072",
            "course_type": "理论+上机",
        }))
        self.assertTrue(is_excluded_course({
            "course_name": "军事技能",
            "course_code": "军009",
            "course_type": "实践",
        }))
        self.assertFalse(is_excluded_course({
            "course_name": "语言程序设计",
            "course_code": "C097",
            "course_type": "理论+上机",
        }))


if __name__ == "__main__":
    unittest.main()
