package com.yuy.eduflow.adjustment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class AdjustmentSuggestionConfirmServiceTests {
	private final AdjustmentRequestService requestService = mock(AdjustmentRequestService.class);
	private final AdjustmentRequestMapper requestMapper = mock(AdjustmentRequestMapper.class);
	private final CourseAssignmentService assignmentService = mock(CourseAssignmentService.class);
	private final CourseAssignmentMapper assignmentMapper = mock(CourseAssignmentMapper.class);
	private final AdjustmentSuggestionConflictDetector conflictDetector = mock(AdjustmentSuggestionConflictDetector.class);
	private final ObjectMapper objectMapper = new ObjectMapper();
	private final AdjustmentSuggestionConfirmService service = new AdjustmentSuggestionConfirmService(
		requestService,
		requestMapper,
		assignmentService,
		assignmentMapper,
		conflictDetector,
		objectMapper
	);

	@Test
	void confirmsSavedValidCandidateOnly() throws Exception {
		AdjustmentSuggestionCandidate candidate = new AdjustmentSuggestionCandidate(0, "候选一", 21L, 31L, true, null);
		AdjustmentRequest request = submittedRequest(savedSuggestions(List.of(
			candidate,
			new AdjustmentSuggestionCandidate(1, "候选二", 22L, 32L, false, "冲突")
		)));
		CourseAssignment assignment = activeAssignment();
		when(requestService.findById(7L)).thenReturn(request);
		when(assignmentService.findById(11L)).thenReturn(assignment);
		when(conflictDetector.detect(assignment, candidate)).thenReturn(candidate);
		when(assignmentMapper.updateSchedule(11L, 21L, 31L)).thenReturn(1);
		when(requestMapper.updateReviewState(7L, "APPROVED", "同意")).thenReturn(1);

		AdjustmentConfirmResult result = service.confirm(7L, new AdjustmentConfirmRequest(0, " 同意 "));

		assertThat(result).isEqualTo(new AdjustmentConfirmResult(7L, 11L, 0, 21L, 31L, "APPROVED", "同意"));
		verify(assignmentMapper).updateSchedule(11L, 21L, 31L);
		verify(requestMapper).updateReviewState(7L, "APPROVED", "同意");
	}

	@Test
	void rejectsUnsavedOrInvalidCandidates() throws Exception {
		AdjustmentRequest request = submittedRequest(savedSuggestions(List.of(
			new AdjustmentSuggestionCandidate(1, "候选二", 22L, 32L, false, "冲突")
		)));
		when(requestService.findById(7L)).thenReturn(request);

		assertThatThrownBy(() -> service.confirm(7L, new AdjustmentConfirmRequest(1, null)))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("只能确认已保存且无冲突的候选方案");
		assertThatThrownBy(() -> service.confirm(7L, new AdjustmentConfirmRequest(99, null)))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("候选方案不存在或尚未生成");

		verifyNoInteractions(assignmentService, assignmentMapper, conflictDetector);
		verify(requestMapper, never()).updateReviewState(7L, "APPROVED", null);
	}

	@Test
	void rejectsSubmittedRequest() {
		AdjustmentRequest request = submittedRequest(null);
		AdjustmentRequest rejected = submittedRequest(null);
		rejected.setStatus("REJECTED");
		rejected.setReviewNote("不满足调课条件");
		when(requestService.findById(7L)).thenReturn(request, rejected);
		when(requestMapper.updateReviewState(7L, "REJECTED", "不满足调课条件")).thenReturn(1);

		AdjustmentRequest result = service.reject(7L, new AdjustmentRejectRequest(" 不满足调课条件 "));

		assertThat(result.getStatus()).isEqualTo("REJECTED");
		assertThat(result.getReviewNote()).isEqualTo("不满足调课条件");
		verify(requestMapper).updateReviewState(7L, "REJECTED", "不满足调课条件");
		verifyNoInteractions(assignmentService, assignmentMapper, conflictDetector);
	}

	private String savedSuggestions(List<AdjustmentSuggestionCandidate> candidates) throws Exception {
		return objectMapper.writeValueAsString(new AdjustmentSuggestionSnapshot(candidates, List.of()));
	}

	private AdjustmentRequest submittedRequest(String aiSuggestion) {
		AdjustmentRequest request = new AdjustmentRequest();
		request.setId(7L);
		request.setAssignmentId(11L);
		request.setTeacherId(3L);
		request.setAiSuggestion(aiSuggestion);
		request.setStatus("SUBMITTED");
		return request;
	}

	private CourseAssignment activeAssignment() {
		CourseAssignment assignment = new CourseAssignment();
		assignment.setId(11L);
		assignment.setTeacherId(3L);
		assignment.setClassGroupId(5L);
		assignment.setStatus("ACTIVE");
		return assignment;
	}
}
