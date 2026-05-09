package com.yuy.eduflow.adjustment;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AdjustmentRequestService {
	private static final String DEFAULT_STATUS = "SUBMITTED";

	private final AdjustmentRequestMapper adjustmentRequestMapper;

	public AdjustmentRequestService(AdjustmentRequestMapper adjustmentRequestMapper) {
		this.adjustmentRequestMapper = adjustmentRequestMapper;
	}

	public List<AdjustmentRequest> findAll(Long assignmentId, Long teacherId, String status) {
		validateOptionalId(assignmentId, "课程安排ID必须大于0");
		validateOptionalId(teacherId, "教师ID必须大于0");
		return adjustmentRequestMapper.findAll(assignmentId, teacherId, status);
	}

	public AdjustmentRequest findById(Long id) {
		AdjustmentRequest request = adjustmentRequestMapper.findById(id);
		if (request == null) {
			throw new IllegalArgumentException("调课申请不存在");
		}
		return request;
	}

	public AdjustmentRequest create(AdjustmentRequestRequest request) {
		AdjustmentRequest adjustmentRequest = toAdjustmentRequest(new AdjustmentRequest(), request);
		adjustmentRequestMapper.insert(adjustmentRequest);
		return findById(adjustmentRequest.getId());
	}

	public AdjustmentRequest update(Long id, AdjustmentRequestRequest request) {
		findById(id);
		AdjustmentRequest adjustmentRequest = toAdjustmentRequest(new AdjustmentRequest(), request);
		adjustmentRequest.setId(id);
		adjustmentRequestMapper.update(adjustmentRequest);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		adjustmentRequestMapper.cancel(id);
	}

	private AdjustmentRequest toAdjustmentRequest(AdjustmentRequest adjustmentRequest, AdjustmentRequestRequest request) {
		requirePositiveId(request.assignmentId(), "课程安排ID不能为空");
		requirePositiveId(request.teacherId(), "教师ID不能为空");
		validateOptionalId(request.preferredTimeSlotId(), "期望时间段ID必须大于0");
		validateOptionalId(request.preferredClassroomId(), "期望教室ID必须大于0");
		if (!StringUtils.hasText(request.reason())) {
			throw new IllegalArgumentException("调课原因不能为空");
		}
		adjustmentRequest.setAssignmentId(request.assignmentId());
		adjustmentRequest.setTeacherId(request.teacherId());
		adjustmentRequest.setReason(request.reason().trim());
		adjustmentRequest.setPreferredTimeText(clean(request.preferredTimeText()));
		adjustmentRequest.setPreferredTimeSlotId(request.preferredTimeSlotId());
		adjustmentRequest.setPreferredClassroomId(request.preferredClassroomId());
		adjustmentRequest.setAiSuggestion(clean(request.aiSuggestion()));
		adjustmentRequest.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : DEFAULT_STATUS);
		adjustmentRequest.setReviewNote(clean(request.reviewNote()));
		return adjustmentRequest;
	}

	private void requirePositiveId(Long id, String emptyMessage) {
		if (id == null) {
			throw new IllegalArgumentException(emptyMessage);
		}
		if (id <= 0) {
			throw new IllegalArgumentException(emptyMessage.replace("不能为空", "必须大于0"));
		}
	}

	private void validateOptionalId(Long id, String message) {
		if (id != null && id <= 0) {
			throw new IllegalArgumentException(message);
		}
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
