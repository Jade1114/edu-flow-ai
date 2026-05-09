package com.yuy.eduflow.assignment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.util.List;
import org.junit.jupiter.api.Test;

class CourseAssignmentServiceTests {
	private final CourseAssignmentMapper courseAssignmentMapper = mock(CourseAssignmentMapper.class);
	private final CourseAssignmentService service = new CourseAssignmentService(courseAssignmentMapper);

	@Test
	void findViewsDefaultsToActiveStatus() {
		List<CourseAssignmentView> expected = List.of(new CourseAssignmentView());
		when(courseAssignmentMapper.findViews(1L, 2L, 3L, 4, 5, "ACTIVE")).thenReturn(expected);

		List<CourseAssignmentView> result = service.findViews(1L, 2L, 3L, 4, 5, null);

		assertThat(result).isSameAs(expected);
		verify(courseAssignmentMapper).findViews(1L, 2L, 3L, 4, 5, "ACTIVE");
	}

	@Test
	void findViewsUsesTrimmedExplicitStatus() {
		when(courseAssignmentMapper.findViews(null, null, null, null, null, "CANCELLED")).thenReturn(List.of());

		List<CourseAssignmentView> result = service.findViews(null, null, null, null, null, " CANCELLED ");

		assertThat(result).isEmpty();
		verify(courseAssignmentMapper).findViews(null, null, null, null, null, "CANCELLED");
	}

	@Test
	void findTeacherAssignmentsUsesTeacherFilterAndActiveStatus() {
		List<CourseAssignmentView> expected = List.of(new CourseAssignmentView());
		when(courseAssignmentMapper.findViews(7L, null, null, 3, 2, "ACTIVE")).thenReturn(expected);

		List<CourseAssignmentView> result = service.findTeacherAssignments(7L, 3, 2);

		assertThat(result).isSameAs(expected);
		verify(courseAssignmentMapper).findViews(7L, null, null, 3, 2, "ACTIVE");
	}

	@Test
	void findClassGroupAssignmentsUsesClassGroupFilterAndActiveStatus() {
		List<CourseAssignmentView> expected = List.of(new CourseAssignmentView());
		when(courseAssignmentMapper.findViews(null, 9L, null, 6, 4, "ACTIVE")).thenReturn(expected);

		List<CourseAssignmentView> result = service.findClassGroupAssignments(9L, 6, 4);

		assertThat(result).isSameAs(expected);
		verify(courseAssignmentMapper).findViews(null, 9L, null, 6, 4, "ACTIVE");
	}

	@Test
	void findViewsRejectsInvalidFiltersBeforeQuerying() {
		assertThatThrownBy(() -> service.findViews(0L, null, null, null, null, null))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("教师ID必须大于0");
		assertThatThrownBy(() -> service.findViews(null, null, null, 19, null, null))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("周次必须在1到18之间");
		assertThatThrownBy(() -> service.findViews(null, null, null, null, 8, null))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("星期必须在1到7之间");

		verifyNoInteractions(courseAssignmentMapper);
	}
}
