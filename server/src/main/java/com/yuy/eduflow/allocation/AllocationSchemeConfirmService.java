package com.yuy.eduflow.allocation;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.common.exception.ConflictException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.AssignmentStatus;
import com.yuy.eduflow.enums.SchemeStatus;
import com.yuy.eduflow.enums.TaskStatus;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AllocationSchemeConfirmService {
	
	
	private static final AssignmentStatus ACTIVE_STATUS = AssignmentStatus.ACTIVE;

	private final AllocationSchemeMapper allocationSchemeMapper;
	private final AllocationItemMapper allocationItemMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final CourseAssignmentMapper courseAssignmentMapper;
	private final AllocationSchemeFeedbackMapper feedbackMapper;

	public AllocationSchemeConfirmService(
		AllocationSchemeMapper allocationSchemeMapper,
		AllocationItemMapper allocationItemMapper,
		AllocationTaskMapper allocationTaskMapper,
		CourseAssignmentMapper courseAssignmentMapper,
		AllocationSchemeFeedbackMapper feedbackMapper
	) {
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.allocationItemMapper = allocationItemMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.courseAssignmentMapper = courseAssignmentMapper;
		this.feedbackMapper = feedbackMapper;
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

		// 如果是重新确认，先清空旧的正式课表
		boolean isReconfirm = scheme.getStatus() == SchemeStatus.CONFIRMED;
		if (isReconfirm) {
			courseAssignmentMapper.deleteBySourceSchemeId(schemeId);
		}

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
		allocationSchemeMapper.rejectOtherCandidates(scheme.getTaskId(), scheme.getId(), SchemeStatus.CANDIDATE.code(), SchemeStatus.REJECTED.code());
		if (allocationTaskMapper.updateStatus(scheme.getTaskId(), SchemeStatus.CONFIRMED.code()) != 1) {
			throw new ConflictException("分课任务状态更新失败");
		}

		// 记录确认反馈
		AllocationSchemeFeedback feedback = new AllocationSchemeFeedback();
		feedback.setSchemeId(schemeId);
		feedback.setTaskId(scheme.getTaskId());
		feedback.setFeedbackType("CONFIRMED");
		feedback.setComment(null);
		feedback.setAdjustmentCount(0);
		feedback.setCreatedBy(null);
		feedbackMapper.insert(feedback);

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
