from __future__ import annotations

import unittest

from python.scheduling_v3.placement_candidates import _select_diverse_candidates


def _candidate(room_id: int, day: int, period: int) -> dict:
    return {"classroom_id": room_id, "day_of_week": day, "period_index": period}


class SchedulingV3PlacementCandidatesTest(unittest.TestCase):
    def test_diverse_selection_limits_room_and_slot_when_possible(self):
        scored = [
            (_candidate(1, 1, 1), 1.0),
            (_candidate(1, 1, 2), 0.99),
            (_candidate(1, 1, 3), 0.98),
            (_candidate(2, 1, 1), 0.97),
            (_candidate(3, 1, 1), 0.96),
            (_candidate(4, 2, 1), 0.95),
            (_candidate(5, 2, 2), 0.94),
        ]

        selected = _select_diverse_candidates(
            scored,
            top_k=4,
            enabled=True,
            max_per_room=1,
            max_per_slot=2,
        )

        rooms = [candidate["classroom_id"] for candidate, _score in selected]
        slots = [(candidate["day_of_week"], candidate["period_index"]) for candidate, _score in selected]
        self.assertEqual(len(selected), 4)
        self.assertLessEqual(max(rooms.count(room) for room in set(rooms)), 1)
        self.assertLessEqual(max(slots.count(slot) for slot in set(slots)), 2)

    def test_diverse_selection_fills_when_limits_are_too_strict(self):
        scored = [
            (_candidate(1, 1, 1), 1.0),
            (_candidate(1, 1, 2), 0.99),
            (_candidate(1, 1, 3), 0.98),
        ]

        selected = _select_diverse_candidates(
            scored,
            top_k=3,
            enabled=True,
            max_per_room=1,
            max_per_slot=1,
        )

        self.assertEqual(len(selected), 3)


if __name__ == "__main__":
    unittest.main()
