"""Core data structures for candidate-pool guided scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TimeSlotRef:
    id: int
    week_number: int
    day_of_week: int
    period_index: int


@dataclass(frozen=True)
class AssignmentRef:
    teaching_task_id: int
    teacher_id: int
    class_group_ids: tuple[int, ...]
    classroom_id: int
    time_slot_id: int
    week_number: int
    day_of_week: int
    period_index: int
    room_rank_score: float = 0.0
    teacher_profile_penalty: float = 0.0
    teacher_profile_penalty_explanation: str = ""


@dataclass(frozen=True)
class TaskCandidate:
    teaching_task_id: int
    candidate_index: int
    assignments: tuple[AssignmentRef, ...]
    template_signature: str
    score: float
    room_rank_score: float
    teacher_profile_penalty: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SchedTask:
    teaching_task_id: int
    teacher_id: int
    teacher_name: str
    total_hours: int
    total_lessons: int
    total_student_count: int
    required_room_type: str
    class_group_ids: tuple[int, ...]
    raw: dict[str, Any]
    teacher_profile: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScheduleContext:
    task_id: int
    task_name: str
    raw_config: dict[str, Any] | None
    scoring_config: dict[str, Any]
    tasks: tuple[SchedTask, ...]
    classrooms: tuple[dict[str, Any], ...]
    time_slots: tuple[dict[str, Any], ...]
    slot_by_coord: dict[tuple[int, int, int], TimeSlotRef]
    allowed_time_slot_ids: frozenset[int]


@dataclass(frozen=True)
class FitnessResult:
    hard_conflicts: int
    quality_score: float
    conflict_summary: dict[str, int]
    assignment_count: int


@dataclass(frozen=True)
class SolvedScheme:
    chromosome: tuple[int, ...]
    fitness: FitnessResult
    assignments: tuple[AssignmentRef, ...]
    scheme_index: int
