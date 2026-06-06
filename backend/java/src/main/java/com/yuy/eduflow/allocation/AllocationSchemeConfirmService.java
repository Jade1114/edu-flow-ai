package com.yuy.eduflow.allocation;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.common.exception.ConflictException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.ml.MlFeedbackEventService;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.AssignmentStatus;
import com.yuy.eduflow.enums.SchemeStatus;
import com.yuy.eduflow.enums.TaskStatus;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
public class AllocationSchemeConfirmService {
	
	
	private static final AssignmentStatus ACTIVE_STATUS = AssignmentStatus.ACTIVE;

	private final AllocationSchemeMapper allocationSchemeMapper;
	private final AllocationItemMapper allocationItemMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final CourseAssignmentMapper courseAssignmentMapper;
	private final AllocationSchemeFeedbackMapper feedbackMapper;
	private final AllocationItemAdjustmentLogMapper adjustmentLogMapper;
	private final MlFeedbackEventService feedbackEventService;

	public AllocationSchemeConfirmService(
		AllocationSchemeMapper allocationSchemeMapper,
		AllocationItemMapper allocationItemMapper,
		AllocationTaskMapper allocationTaskMapper,
		CourseAssignmentMapper courseAssignmentMapper,
		AllocationSchemeFeedbackMapper feedbackMapper,
		AllocationItemAdjustmentLogMapper adjustmentLogMapper,
		MlFeedbackEventService feedbackEventService
	) {
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.allocationItemMapper = allocationItemMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.courseAssignmentMapper = courseAssignmentMapper;
		this.feedbackMapper = feedbackMapper;
		this.adjustmentLogMapper = adjustmentLogMapper;
		this.feedbackEventService = feedbackEventService;
	}

	@Transactional
	public AllocationConfirmResult confirm(Long schemeId) {
		AllocationScheme scheme = allocationSchemeMapper.findById(schemeId);
		if (scheme == null) {
			throw new ResourceNotFoundException("分课方案不存在");
		}
		if (!Boolean.TRUE.equals(scheme.getValid())) {
			throw new ConflictException("分课方案存在冲突，不能确认");
		}

		List<AllocationItem> items = allocationItemMapper.findAll(scheme.getId(), null, null, null);
		if (items.isEmpty()) {
			throw new ValidationException("分课方案明细为空，不能确认");
		}
		for (AllocationItem item : items) {
			if (!Boolean.TRUE.equals(item.getValid())) {
				throw new ValidationException("分课方案存在冲突明细，不能确认：明细ID " + item.getId());
			}
		}

		int inactivatedAssignments = courseAssignmentMapper.inactivateByAllocationTaskId(
			scheme.getTaskId(),
			AssignmentStatus.INACTIVE.code()
		);
		log.info("Confirming allocation scheme: schemeId={}, taskId={}, inactivatedOldAssignments={}",
			schemeId, scheme.getTaskId(), inactivatedAssignments);

		int assignmentCount = 0;
		for (AllocationItem item : items) {
			CourseAssignment assignment = toAssignment(scheme.getId(), item);
			int inserted = courseAssignmentMapper.insert(assignment);
			if (inserted != 1) {
				throw new ConflictException("正式课表写入失败");
			}
			assignmentCount++;
		}

		if (allocationSchemeMapper.updateStatus(scheme.getId(), SchemeStatus.CONFIRMED.code()) != 1) {
			throw new ConflictException("分课方案状态更新失败");
		}
		int rejectedSchemes = allocationSchemeMapper.rejectOtherSelectableSchemes(
			scheme.getTaskId(),
			scheme.getId(),
			SchemeStatus.REJECTED.code()
		);
		log.info("Allocation scheme confirmed: schemeId={}, insertedAssignments={}, rejectedOtherSchemes={}",
			scheme.getId(), assignmentCount, rejectedSchemes);
		if (allocationTaskMapper.updateStatus(scheme.getTaskId(), SchemeStatus.CONFIRMED.code()) != 1) {
			throw new ConflictException("分课任务状态更新失败");
		}

		// 记录确认反馈
		AllocationSchemeFeedback feedback = new AllocationSchemeFeedback();
		feedback.setSchemeId(schemeId);
		feedback.setTaskId(scheme.getTaskId());
		feedback.setFeedbackType("CONFIRMED");
		feedback.setAdjustmentCount(adjustmentLogMapper.countBySchemeId(schemeId));
		feedback.setCreatedBy(null);
		feedbackMapper.insert(feedback);
		feedbackEventService.recordSchemeConfirmed(scheme, feedback.getId());

		return new AllocationConfirmResult(
			scheme.getId(),
			scheme.getTaskId(),
			assignmentCount,
			SchemeStatus.CONFIRMED.code(),
			SchemeStatus.CONFIRMED.code()
		);
	}

	private CourseAssignment toAssignment(Long schemeId, AllocationItem item) {
		CourseAssignment assignment = new CourseAssignment();
		assignment.setSourceSchemeId(schemeId);
		assignment.setTeachingTaskId(item.getTeachingTaskId());
		assignment.setClassroomId(item.getClassroomId());
		assignment.setTimeSlotId(item.getTimeSlotId());
		assignment.setStatus(ACTIVE_STATUS);
		return assignment;
	}
}
