package com.yuy.eduflow.allocation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class AllocationSchemeConfirmServiceTests {
	private final AllocationSchemeMapper schemeMapper = mock(AllocationSchemeMapper.class);
	private final AllocationItemMapper itemMapper = mock(AllocationItemMapper.class);
	private final AllocationTaskMapper taskMapper = mock(AllocationTaskMapper.class);
	private final CourseAssignmentMapper assignmentMapper = mock(CourseAssignmentMapper.class);
	private final AllocationSchemeConfirmService service = new AllocationSchemeConfirmService(
		schemeMapper,
		itemMapper,
		taskMapper,
		assignmentMapper
	);

	@Test
	void confirmsValidCandidateAndWritesAssignments() {
		when(schemeMapper.findById(11L)).thenReturn(scheme(11L, 1L, "CANDIDATE", true));
		when(itemMapper.findAll(11L, null, null, null, null)).thenReturn(List.of(
			item(101L, 1L, 1L, 1L, 1L, 1L, true),
			item(102L, 2L, 2L, 2L, 2L, 2L, true)
		));
		when(assignmentMapper.insert(any(CourseAssignment.class))).thenReturn(1);
		when(schemeMapper.updateStatus(11L, "CONFIRMED")).thenReturn(1);
		when(schemeMapper.rejectOtherCandidates(1L, 11L)).thenReturn(2);
		when(taskMapper.updateStatus(1L, "CONFIRMED")).thenReturn(1);

		AllocationConfirmResult result = service.confirm(11L);

		assertThat(result).isEqualTo(new AllocationConfirmResult(11L, 1L, 2, "CONFIRMED", "CONFIRMED"));
		ArgumentCaptor<CourseAssignment> assignmentCaptor = ArgumentCaptor.forClass(CourseAssignment.class);
		verify(assignmentMapper, times(2)).insert(assignmentCaptor.capture());
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getSourceSchemeId)
			.containsExactly(11L, 11L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getCourseId)
			.containsExactly(1L, 2L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getClassGroupId)
			.containsExactly(1L, 2L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getTeacherId)
			.containsExactly(1L, 2L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getClassroomId)
			.containsExactly(1L, 2L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getTimeSlotId)
			.containsExactly(1L, 2L);
		assertThat(assignmentCaptor.getAllValues())
			.extracting(CourseAssignment::getStatus)
			.containsExactly("ACTIVE", "ACTIVE");
		verify(schemeMapper).updateStatus(11L, "CONFIRMED");
		verify(schemeMapper).rejectOtherCandidates(1L, 11L);
		verify(taskMapper).updateStatus(1L, "CONFIRMED");
	}

	@Test
	void rejectsInvalidScheme() {
		when(schemeMapper.findById(11L)).thenReturn(scheme(11L, 1L, "CANDIDATE", false));

		assertThatThrownBy(() -> service.confirm(11L))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("分课方案存在冲突，不能确认");

		verifyNoInteractions(itemMapper, assignmentMapper, taskMapper);
		verify(schemeMapper, never()).updateStatus(any(), any());
		verify(schemeMapper, never()).rejectOtherCandidates(any(), any());
	}

	@Test
	void rejectsSchemeWithConflictItem() {
		when(schemeMapper.findById(11L)).thenReturn(scheme(11L, 1L, "CANDIDATE", true));
		when(itemMapper.findAll(11L, null, null, null, null)).thenReturn(List.of(
			item(101L, 1L, 1L, 1L, 1L, 1L, true),
			item(102L, 2L, 2L, 2L, 2L, 2L, false)
		));

		assertThatThrownBy(() -> service.confirm(11L))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("分课方案存在冲突明细，不能确认：明细ID 102");

		verifyNoInteractions(assignmentMapper, taskMapper);
		verify(schemeMapper, never()).updateStatus(any(), any());
		verify(schemeMapper, never()).rejectOtherCandidates(any(), any());
	}

	@Test
	void rejectsSchemeWithoutItems() {
		when(schemeMapper.findById(11L)).thenReturn(scheme(11L, 1L, "CANDIDATE", true));
		when(itemMapper.findAll(11L, null, null, null, null)).thenReturn(List.of());

		assertThatThrownBy(() -> service.confirm(11L))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("分课方案明细为空，不能确认");

		verifyNoInteractions(assignmentMapper, taskMapper);
		verify(schemeMapper, never()).updateStatus(any(), any());
		verify(schemeMapper, never()).rejectOtherCandidates(any(), any());
	}

	@Test
	void rejectsAlreadyConfirmedSchemeToAvoidDuplicateAssignments() {
		when(schemeMapper.findById(11L)).thenReturn(scheme(11L, 1L, "CONFIRMED", true));

		assertThatThrownBy(() -> service.confirm(11L))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("分课方案已确认，不能重复确认");

		verifyNoInteractions(itemMapper, assignmentMapper, taskMapper);
	}

	private AllocationScheme scheme(Long id, Long taskId, String status, Boolean valid) {
		AllocationScheme scheme = new AllocationScheme();
		scheme.setId(id);
		scheme.setTaskId(taskId);
		scheme.setStatus(status);
		scheme.setValid(valid);
		return scheme;
	}

	private AllocationItem item(
		Long id,
		Long courseId,
		Long classGroupId,
		Long teacherId,
		Long classroomId,
		Long timeSlotId,
		Boolean valid
	) {
		AllocationItem item = new AllocationItem();
		item.setId(id);
		item.setCourseId(courseId);
		item.setClassGroupId(classGroupId);
		item.setTeacherId(teacherId);
		item.setClassroomId(classroomId);
		item.setTimeSlotId(timeSlotId);
		item.setValid(valid);
		return item;
	}
}
