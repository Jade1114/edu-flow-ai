"""Assignment-level LightGBM scorer for GA scheduling.

The scorer is intentionally optional: missing model/dependencies degrade to 0.0 scores so
GA generation remains available in development and fresh environments.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ml.scheduling.infra.constants import (
    BASE_FEATURE_SCHEMA_PATH,
    BASE_MODEL_PATH,
    FEEDBACK_FEATURE_SCHEMA_PATH,
    FEEDBACK_MODEL_PATH,
)
from ml.scheduling.types import AllocationTask, Template, slot_to_day_period

_log = logging.getLogger("ga")


class AssignmentScorer:
    """Score ``task × template × slot × classroom`` candidates with cache."""

    def __init__(
        self,
        task_data_by_id: dict[int, dict[str, Any]] | None = None,
        classroom_by_id: dict[int, dict[str, Any]] | None = None,
        *,
        model_path: Path | None = None,
        feature_schema_path: Path | None = None,
    ) -> None:
        self.task_data_by_id = task_data_by_id or {}
        self.classroom_by_id = classroom_by_id or {}
        resolved_model, resolved_schema = _resolve_model_artifacts(model_path, feature_schema_path)
        self.model_path = resolved_model
        self.feature_schema_path = resolved_schema
        self._cache: dict[tuple[int, tuple[int, ...], int, int], float] = {}
        self._model = None
        self._feature_columns: list[str] = []
        self._categorical_columns: list[str] = []
        self._pd = None
        self._disabled_reason = ""
        self._load_optional_model()

    @property
    def enabled(self) -> bool:
        return self._model is not None and bool(self._feature_columns)

    @property
    def model_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model_path": str(self.model_path),
            "feature_schema_path": str(self.feature_schema_path),
            "feature_count": len(self._feature_columns),
            "categorical_feature_count": len(self._categorical_columns),
            "cache_size": len(self._cache),
            "disabled_reason": self._disabled_reason,
        }

    def score(self, task: AllocationTask, template: Template, slot_id: int, classroom_id: int) -> float:
        """Return a normalized local quality score. Missing model returns 0.0."""
        if not self.enabled:
            return 0.0

        key = (task.task_id, tuple(template.weeks_list), slot_id, classroom_id)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            rows = [
                self._build_feature_row(task, week_number, slot_id, classroom_id)
                for week_number in template.weeks_list
            ]
            frame = self._pd.DataFrame(rows)
            for column in self._feature_columns:
                if column not in frame.columns:
                    frame[column] = "" if column in self._categorical_columns else 0
            frame = frame[self._feature_columns]
            for column in self._categorical_columns:
                if column in frame.columns:
                    frame[column] = frame[column].astype("category")
            predictions = self._model.predict(frame)
            score = float(sum(predictions) / len(predictions)) if len(predictions) else 0.0
            score = max(0.0, min(1.0, score))
        except Exception as exc:  # pragma: no cover - defensive fallback
            _log.debug("LightGBM assignment scoring disabled for candidate: %s", exc)
            score = 0.0

        self._cache[key] = score
        return score

    def _load_optional_model(self) -> None:
        if not self.model_path.exists() or not self.feature_schema_path.exists():
            self._disabled_reason = "model/schema not found"
            _log.info("LightGBM assignment scorer disabled: %s", self._disabled_reason)
            return

        try:
            import lightgbm as lgb  # type: ignore
            import pandas as pd  # type: ignore

            with self.feature_schema_path.open("r", encoding="utf-8") as file:
                schema = json.load(file)
            self._feature_columns = list(schema.get("feature_columns") or [])
            self._categorical_columns = list(schema.get("categorical_columns") or [])
            self._model = lgb.Booster(model_file=str(self.model_path))
            self._pd = pd
            self._disabled_reason = ""
            _log.info("LightGBM assignment scorer enabled: %s", self.model_path)
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._disabled_reason = str(exc)
            _log.info("LightGBM assignment scorer disabled: %s", self._disabled_reason)
            self._model = None
            self._feature_columns = []
            self._categorical_columns = []
            self._pd = None

    def _build_feature_row(
        self,
        task: AllocationTask,
        week_number: int,
        slot_id: int,
        classroom_id: int,
    ) -> dict[str, Any]:
        task_data = self.task_data_by_id.get(task.task_id, {})
        classroom = self.classroom_by_id.get(classroom_id, {})
        day_of_week, period_index = slot_to_day_period(slot_id)
        profile = task.teacher_profile or {}

        room_capacity = int(classroom.get("capacity") or 0)
        total_student_count = task.student_count
        required_room_type = str(task_data.get("required_room_type") or "")
        room_type = str(classroom.get("classroom_type") or "")
        capacity_margin = room_capacity - total_student_count
        capacity_ratio = round(total_student_count / room_capacity, 4) if room_capacity > 0 else 1.0
        capacity_enough = room_capacity >= total_student_count if room_capacity > 0 else False
        type_match = (not required_room_type) or required_room_type.strip().lower() == room_type.strip().lower()

        preferred_weekdays = set(profile.get("preferred_weekdays") or [])
        avoid_periods = set(profile.get("avoid_periods") or [])
        hard_unavailable = set(profile.get("hard_unavailable") or [])
        soft_avoid = profile.get("soft_avoid") or []
        teacher_avoid_slot_match = int(
            period_index in avoid_periods
            or any(
                isinstance(item, dict)
                and int(item.get("weekday") or 0) == day_of_week
                and period_index in set(item.get("periods") or [])
                for item in soft_avoid
            )
        )

        return {
            "course_type": task_data.get("course_type") or "",
            "total_hours": int(task_data.get("total_hours") or task.total_lessons * 2),
            "required_room_type": required_room_type,
            "class_group_count": int(task_data.get("class_group_count") or 1),
            "total_student_count": total_student_count,
            "teacher_department": task_data.get("teacher_department") or "",
            "teacher_title": task_data.get("teacher_title") or "",
            "teacher_max_weekly_hours": int(task_data.get("teacher_max_weekly_hours") or 0),
            "room_capacity": room_capacity,
            "room_type": room_type,
            "room_building": classroom.get("building") or "",
            "capacity_margin": capacity_margin,
            "capacity_ratio": capacity_ratio,
            "week_number": week_number,
            "day_of_week": day_of_week,
            "period_index": period_index,
            "is_morning": int(period_index <= 2),
            "is_afternoon": int(period_index == 3),
            "is_evening": int(period_index >= 4),
            "is_weekend": int(day_of_week >= 6),
            "is_early_period": int(period_index == 1),
            "is_late_period": int(period_index >= 4),
            "required_fragments": task.total_lessons,
            "teacher_matrix_value": -1 if (day_of_week, period_index) in hard_unavailable else 0,
            "teacher_preferred_max_weekly_hours": int(profile.get("max_weekly_lessons") or task_data.get("teacher_preferred_max_weekly_hours") or 0),
            "teacher_avoid_first_period": int(1 in avoid_periods),
            "teacher_avoid_last_period": int(5 in avoid_periods),
            "teacher_prefer_compact_schedule": int(bool(profile.get("prefer_compact_schedule"))),
            "teacher_preferred_weekday_match": int(day_of_week in preferred_weekdays) if preferred_weekdays else 0,
            "teacher_avoid_slot_match": teacher_avoid_slot_match,
            "teacher_occupied_at_slot": 0,
            "class_occupied_at_slot": 0,
            "room_occupied_at_slot": 0,
            "teacher_day_load": 0,
            "class_day_load": 0,
            "teacher_week_load": 0,
            "class_week_load": 0,
            "scheme_day_load": 0,
            "room_day_load": 0,
            "room_week_load": 0,
            "task_day_load": 0,
            "is_capacity_enough": int(capacity_enough),
            "is_room_type_match": int(type_match),
            "has_teacher_conflict": 0,
            "has_class_conflict": 0,
            "has_room_conflict": 0,
            "has_hard_conflict": int((not capacity_enough) or (not type_match)),
        }


def _resolve_model_artifacts(
    model_path: Path | None,
    feature_schema_path: Path | None,
) -> tuple[Path, Path]:
    if model_path is not None or feature_schema_path is not None:
        return model_path or BASE_MODEL_PATH, feature_schema_path or BASE_FEATURE_SCHEMA_PATH
    if FEEDBACK_MODEL_PATH.exists() and FEEDBACK_FEATURE_SCHEMA_PATH.exists():
        return FEEDBACK_MODEL_PATH, FEEDBACK_FEATURE_SCHEMA_PATH
    return BASE_MODEL_PATH, BASE_FEATURE_SCHEMA_PATH
