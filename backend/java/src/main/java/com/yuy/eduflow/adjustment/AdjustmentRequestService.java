package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.enums.AdjustmentStatus;
import com.yuy.eduflow.ml.MlFeedbackEventService;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AdjustmentRequestService {

    private final AdjustmentRequestMapper adjustmentRequestMapper;
    private final CourseAssignmentService courseAssignmentService;
    private final MlFeedbackEventService feedbackEventService;

    public AdjustmentRequestService(
        AdjustmentRequestMapper adjustmentRequestMapper,
        CourseAssignmentService courseAssignmentService,
        MlFeedbackEventService feedbackEventService
    ) {
        this.adjustmentRequestMapper = adjustmentRequestMapper;
        this.courseAssignmentService = courseAssignmentService;
        this.feedbackEventService = feedbackEventService;
    }

    // ==================== CRUD ====================

    public List<AdjustmentRequest> findAll(String status, Long teacherId) {
        return adjustmentRequestMapper.findAll(status, teacherId);
    }

    public AdjustmentRequest findById(Long id) {
        AdjustmentRequest req = adjustmentRequestMapper.findById(id);
        if (req == null) throw new ResourceNotFoundException("调课申请不存在");
        return req;
    }

    @Transactional
    public AdjustmentRequest create(AdjustmentRequestRequest request) {
        CourseAssignment assignment = courseAssignmentService.findById(request.assignmentId());

        AdjustmentRequest entity = new AdjustmentRequest();
        entity.setAssignmentId(request.assignmentId());
        entity.setTeacherId(assignment.getTeacherId());
        entity.setReason(request.reason());
        entity.setPreferredTimeText(request.preferredTimeText());
        adjustmentRequestMapper.insert(entity);
        return findById(entity.getId());
    }

    // ==================== Confirm / Reject ====================

    @Transactional
    public void confirm(Long requestId, AdjustmentConfirmRequest confirmReq) {
        AdjustmentRequest request = findById(requestId);
        CourseAssignment assignment = courseAssignmentService.findById(request.getAssignmentId());
        String reviewNote = confirmReq == null ? null : confirmReq.reviewNote();
        adjustmentRequestMapper.updateReview(requestId, "APPROVED", reviewNote);
        request.setStatus(AdjustmentStatus.APPROVED);
        request.setReviewNote(reviewNote);
        feedbackEventService.recordAdjustmentApproved(request, assignment, reviewNote);
    }

    @Transactional
    public void reject(Long requestId, AdjustmentRejectRequest rejectReq) {
        AdjustmentRequest request = findById(requestId);
        CourseAssignment assignment = courseAssignmentService.findById(request.getAssignmentId());
        String reviewNote = rejectReq == null ? null : rejectReq.reviewNote();
        adjustmentRequestMapper.updateReview(requestId, "REJECTED", reviewNote);
        request.setStatus(AdjustmentStatus.REJECTED);
        request.setReviewNote(reviewNote);
        feedbackEventService.recordAdjustmentRejected(request, assignment, reviewNote);
    }
}
