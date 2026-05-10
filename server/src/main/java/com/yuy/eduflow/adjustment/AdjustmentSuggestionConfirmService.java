package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Service
public class AdjustmentSuggestionConfirmService {
	private static final String ACTIVE_STATUS = "ACTIVE";
	private static final String SUBMITTED_STATUS = "SUBMITTED";
	private static final String APPROVED_STATUS = "APPROVED";
	private static final String REJECTED_STATUS = "REJECTED";

	private final AdjustmentRequestService adjustmentRequestService;
	private final AdjustmentRequestMapper adjustmentRequestMapper;
	private final CourseAssignmentService courseAssignmentService;
	private final CourseAssignmentMapper courseAssignmentMapper;
	private final AdjustmentSuggestionConflictDetector conflictDetector;
	private final ObjectMapper objectMapper;

	public AdjustmentSuggestionConfirmService(
		AdjustmentRequestService adjustmentRequestService,
		AdjustmentRequestMapper adjustmentRequestMapper,
		CourseAssignmentService courseAssignmentService,
		CourseAssignmentMapper courseAssignmentMapper,
		AdjustmentSuggestionConflictDetector conflictDetector,
		ObjectMapper objectMapper
	) {
		this.adjustmentRequestService = adjustmentRequestService;
		this.adjustmentRequestMapper = adjustmentRequestMapper;
		this.courseAssignmentService = courseAssignmentService;
		this.courseAssignmentMapper = courseAssignmentMapper;
		this.conflictDetector = conflictDetector;
		this.objectMapper = objectMapper;
	}

	@Transactional
	public AdjustmentConfirmResult confirm(Long requestId, AdjustmentConfirmRequest confirmRequest) {
		AdjustmentRequest request = adjustmentRequestService.findById(requestId);
		requireSubmitted(request, "只有 SUBMITTED 状态的调课申请可以确认候选方案");
		Integer candidateIndex = confirmRequest == null ? null : confirmRequest.candidateIndex();
		if (candidateIndex == null) {
			throw new IllegalArgumentException("候选方案序号不能为空");
		}
		AdjustmentSuggestionCandidate candidate = findSavedCandidate(request, candidateIndex);
		if (!Boolean.TRUE.equals(candidate.valid())) {
			throw new IllegalArgumentException("只能确认已保存且无冲突的候选方案");
		}

		CourseAssignment originalAssignment = courseAssignmentService.findById(request.getAssignmentId());
		validateRequestMatchesAssignment(request, originalAssignment);
		AdjustmentSuggestionCandidate currentCheckedCandidate = conflictDetector.detect(originalAssignment, candidate);
		if (!Boolean.TRUE.equals(currentCheckedCandidate.valid())) {
			throw new IllegalArgumentException("候选方案当前存在冲突：" + currentCheckedCandidate.conflictMessage());
		}

		if (courseAssignmentMapper.updateSchedule(
				originalAssignment.getId(),
				candidate.newTimeSlotId(),
				candidate.newClassroomId()
			) != 1) {
			throw new IllegalArgumentException("正式课表更新失败");
		}
		String reviewNote = clean(confirmRequest.reviewNote());
		if (adjustmentRequestMapper.updateReviewState(request.getId(), APPROVED_STATUS, reviewNote) != 1) {
			throw new IllegalArgumentException("调课申请状态更新失败");
		}
		return new AdjustmentConfirmResult(
			request.getId(),
			originalAssignment.getId(),
			candidate.candidateIndex(),
			candidate.newTimeSlotId(),
			candidate.newClassroomId(),
			APPROVED_STATUS,
			reviewNote
		);
	}

	@Transactional
	public AdjustmentRequest reject(Long requestId, AdjustmentRejectRequest rejectRequest) {
		AdjustmentRequest request = adjustmentRequestService.findById(requestId);
		requireSubmitted(request, "只有 SUBMITTED 状态的调课申请可以拒绝");
		String reviewNote = clean(rejectRequest == null ? null : rejectRequest.reviewNote());
		if (adjustmentRequestMapper.updateReviewState(request.getId(), REJECTED_STATUS, reviewNote) != 1) {
			throw new IllegalArgumentException("调课申请状态更新失败");
		}
		return adjustmentRequestService.findById(requestId);
	}

	private AdjustmentSuggestionCandidate findSavedCandidate(AdjustmentRequest request, Integer candidateIndex) {
		AdjustmentSuggestionSnapshot snapshot = readSuggestionSnapshot(request.getAiSuggestion());
		List<AdjustmentSuggestionCandidate> candidates = snapshot.candidates() == null
			? List.of()
			: snapshot.candidates();
		return candidates.stream()
			.filter(candidate -> candidateIndex.equals(candidate.candidateIndex()))
			.findFirst()
			.orElseThrow(() -> new IllegalArgumentException("候选方案不存在或尚未生成"));
	}

	private AdjustmentSuggestionSnapshot readSuggestionSnapshot(String aiSuggestion) {
		if (!StringUtils.hasText(aiSuggestion)) {
			throw new IllegalArgumentException("尚未生成调课候选方案，不能确认");
		}
		try {
			return objectMapper.readValue(aiSuggestion, AdjustmentSuggestionSnapshot.class);
		} catch (JacksonException exception) {
			throw new IllegalArgumentException("已保存调课候选 JSON 解析失败：" + exception.getOriginalMessage());
		}
	}

	private void requireSubmitted(AdjustmentRequest request, String message) {
		if (!SUBMITTED_STATUS.equals(request.getStatus())) {
			throw new IllegalArgumentException(message);
		}
	}

	private void validateRequestMatchesAssignment(AdjustmentRequest request, CourseAssignment assignment) {
		if (!request.getTeacherId().equals(assignment.getTeacherId())) {
			throw new IllegalArgumentException("调课申请教师与原课程安排教师不一致");
		}
		if (!ACTIVE_STATUS.equals(assignment.getStatus())) {
			throw new IllegalArgumentException("原课程安排不是 ACTIVE 状态，不能确认调课");
		}
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
