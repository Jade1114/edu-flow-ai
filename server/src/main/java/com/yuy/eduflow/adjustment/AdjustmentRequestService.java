package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AdjustmentRequestService {

    private final AdjustmentRequestMapper adjustmentRequestMapper;
    private final CourseAssignmentService courseAssignmentService;

    public AdjustmentRequestService(
        AdjustmentRequestMapper adjustmentRequestMapper,
        CourseAssignmentService courseAssignmentService
    ) {
        this.adjustmentRequestMapper = adjustmentRequestMapper;
        this.courseAssignmentService = courseAssignmentService;
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
        findById(requestId);
        adjustmentRequestMapper.updateReview(requestId, "APPROVED", confirmReq.reviewNote());
    }

    @Transactional
    public void reject(Long requestId, AdjustmentRejectRequest rejectReq) {
        findById(requestId);
        adjustmentRequestMapper.updateReview(requestId, "REJECTED", rejectReq.reviewNote());
    }
}
