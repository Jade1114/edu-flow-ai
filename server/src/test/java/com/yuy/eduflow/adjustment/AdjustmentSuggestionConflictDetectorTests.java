package com.yuy.eduflow.adjustment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import org.junit.jupiter.api.Test;

class AdjustmentSuggestionConflictDetectorTests {

	@Test
	void marksCandidateInvalidWhenFormalScheduleHasConflicts() {
		CourseAssignmentMapper mapper = mock(CourseAssignmentMapper.class);
		AdjustmentSuggestionConflictDetector detector = new AdjustmentSuggestionConflictDetector(mapper);
		CourseAssignment assignment = assignment();
		when(mapper.countActiveTeacherTimeConflict(10L, 1L, 20L)).thenReturn(1);
		when(mapper.countActiveClassGroupTimeConflict(10L, 2L, 20L)).thenReturn(0);
		when(mapper.countActiveClassroomTimeConflict(10L, 30L, 20L)).thenReturn(2);

		AdjustmentSuggestionCandidate result = detector.detect(
			assignment,
			new AdjustmentSuggestionCandidate(0, "候选", 20L, 30L, true, null)
		);

		assertThat(result.valid()).isFalse();
		assertThat(result.conflictMessage())
			.contains("教师在目标时间段已有其他 ACTIVE 课程安排（1 条）")
			.contains("教室在目标时间段已有其他 ACTIVE 课程安排（2 条）");
	}

	private CourseAssignment assignment() {
		CourseAssignment assignment = new CourseAssignment();
		assignment.setId(10L);
		assignment.setTeacherId(1L);
		assignment.setClassGroupId(2L);
		assignment.setStatus("ACTIVE");
		return assignment;
	}
}
