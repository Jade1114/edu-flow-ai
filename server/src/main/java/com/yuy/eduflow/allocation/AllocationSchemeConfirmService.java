package com.yuy.eduflow.allocation;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AllocationSchemeConfirmService {
	private static final String CANDIDATE_STATUS = "CANDIDATE";
	private static final String CONFIRMED_STATUS = "CONFIRMED";
	private static final String ACTIVE_STATUS = "ACTIVE";

	private final AllocationSchemeMapper allocationSchemeMapper;
	private final AllocationItemMapper allocationItemMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final CourseAssignmentMapper courseAssignmentMapper;

	public AllocationSchemeConfirmService(
		AllocationSchemeMapper allocationSchemeMapper,
		AllocationItemMapper allocationItemMapper,
		AllocationTaskMapper allocationTaskMapper,
		CourseAssignmentMapper courseAssignmentMapper
	) {
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.allocationItemMapper = allocationItemMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.courseAssignmentMapper = courseAssignmentMapper;
	}

	@Transactional
	public AllocationConfirmResult confirm(Long schemeId) {
		AllocationScheme scheme = allocationSchemeMapper.findById(schemeId);
		if (scheme == null) {
			throw new IllegalArgumentException("分课方案不存在");
		}
		if (CONFIRMED_STATUS.equals(scheme.getStatus())) {
			throw new IllegalArgumentException("分课方案已确认，不能重复确认");
		}
		if (!CANDIDATE_STATUS.equals(scheme.getStatus())) {
			throw new IllegalArgumentException("只有候选分课方案可以确认");
		}
		if (!Boolean.TRUE.equals(scheme.getValid())) {
			throw new IllegalArgumentException("分课方案存在冲突，不能确认");
		}

		List<AllocationItem> items = allocationItemMapper.findAll(scheme.getId(), null, null, null, null);
		if (items.isEmpty()) {
			throw new IllegalArgumentException("分课方案明细为空，不能确认");
		}
		for (AllocationItem item : items) {
			if (!Boolean.TRUE.equals(item.getValid())) {
				throw new IllegalArgumentException("分课方案存在冲突明细，不能确认：明细ID " + item.getId());
			}
		}

		int assignmentCount = 0;
		for (AllocationItem item : items) {
			CourseAssignment assignment = toAssignment(scheme.getId(), item);
			int inserted = courseAssignmentMapper.insert(assignment);
			if (inserted != 1) {
				throw new IllegalArgumentException("正式课表写入失败");
			}
			assignmentCount++;
		}

		if (allocationSchemeMapper.updateStatus(scheme.getId(), CONFIRMED_STATUS) != 1) {
			throw new IllegalArgumentException("分课方案状态更新失败");
		}
		allocationSchemeMapper.rejectOtherCandidates(scheme.getTaskId(), scheme.getId());
		if (allocationTaskMapper.updateStatus(scheme.getTaskId(), CONFIRMED_STATUS) != 1) {
			throw new IllegalArgumentException("分课任务状态更新失败");
		}

		return new AllocationConfirmResult(
			scheme.getId(),
			scheme.getTaskId(),
			assignmentCount,
			CONFIRMED_STATUS,
			CONFIRMED_STATUS
		);
	}

	private CourseAssignment toAssignment(Long schemeId, AllocationItem item) {
		CourseAssignment assignment = new CourseAssignment();
		assignment.setSourceSchemeId(schemeId);
		assignment.setCourseId(item.getCourseId());
		assignment.setClassGroupId(item.getClassGroupId());
		assignment.setTeacherId(item.getTeacherId());
		assignment.setClassroomId(item.getClassroomId());
		assignment.setTimeSlotId(item.getTimeSlotId());
		assignment.setStatus(ACTIVE_STATUS);
		return assignment;
	}
}
