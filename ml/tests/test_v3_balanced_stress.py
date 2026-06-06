from __future__ import annotations

import unittest

from ml.scripts.v3_balanced_stress import StressProfile, _balanced_rows, _distribution


class V3BalancedStressTest(unittest.TestCase):
    def test_balanced_rows_spread_teachers_classes_and_courses(self):
        teachers = [{"id": i, "name": f"T{i}"} for i in range(1, 9)]
        class_groups = [{"id": i, "name": f"C{i}"} for i in range(101, 117)]
        courses = [{"id": i, "code": f"K{i}", "required_room_type": "普通教室"} for i in range(201, 221)]

        rows = _balanced_rows(
            task_count=400,
            teachers=teachers,
            class_groups=class_groups,
            courses=courses,
            total_hours=2,
        )
        distribution = _distribution(rows)

        self.assertEqual(len(rows), 400)
        self.assertLessEqual(distribution["teacher"]["max_minus_min"], 1)
        self.assertLessEqual(distribution["class_group"]["max_minus_min"], 1)
        self.assertLessEqual(distribution["course"]["max_minus_min"], 1)

    def test_auto_defaults_stop_after_quality(self):
        try:
            from ml.scheduling_v3.pipeline import _resolve_max_auto_stage, _widen_first_feasible_candidates
        except SystemExit as exc:
            self.skipTest(str(exc))
        self.assertEqual(
            _resolve_max_auto_stage(None, requested_generation_mode="AUTO", skip_diversity=False),
            "QUALITY_OPTIMIZATION",
        )
        self.assertEqual(
            _resolve_max_auto_stage(None, requested_generation_mode="AUTO_FULL", skip_diversity=False),
            "DIVERSITY_SEARCH",
        )
        self.assertEqual(
            _widen_first_feasible_candidates(
                task_count=4000,
                generation_mode="FEASIBILITY",
                placement_top_k=24,
                raw_plan_count=24,
                cp_plan_count=6,
            ),
            (64, 64, 16),
        )
        self.assertEqual(
            _widen_first_feasible_candidates(
                task_count=4000,
                generation_mode="QUALITY",
                placement_top_k=24,
                raw_plan_count=24,
                cp_plan_count=6,
            ),
            (24, 24, 6),
        )

    def test_4000_profile_uses_wider_feasibility_candidates(self):
        self.assertEqual(StressProfile.placement_top_k, 64)
        self.assertEqual(StressProfile.raw_plan_count, 64)
        self.assertEqual(StressProfile.cp_plan_count, 16)

    def test_infeasible_with_clean_preflight_reports_candidate_coverage(self):
        try:
            from ml.scheduling_v3.cp_sat_selector import _candidate_coverage_diagnosis
        except SystemExit as exc:
            self.skipTest(str(exc))

        diagnosis = _candidate_coverage_diagnosis(
            solver_status="INFEASIBLE",
            scheme_count=0,
            summary_context={
                "placement_top_k": 24,
                "raw_plan_count": 24,
                "cp_plan_count": 6,
                "preflight_no_candidate_task_count": 0,
                "preflight_no_plan_task_count": 0,
            },
        )

        self.assertIsNotNone(diagnosis)
        assert diagnosis is not None
        self.assertEqual(diagnosis["type"], "CANDIDATE_COVERAGE_INSUFFICIENT")
        self.assertIn("coverage is too narrow", diagnosis["message"])
        self.assertIn("Increase placement_top_k/raw_plan_count", diagnosis["recommendation"])


if __name__ == "__main__":
    unittest.main()
