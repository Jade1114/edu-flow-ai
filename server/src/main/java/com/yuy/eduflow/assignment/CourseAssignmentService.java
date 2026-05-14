package com.yuy.eduflow.assignment;

import com.yuy.eduflow.common.Assert;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.AssignmentStatus;
import org.springframework.util.StringUtils;

@Service
public class CourseAssignmentService {
	

	private final CourseAssignmentMapper courseAssignmentMapper;

	public CourseAssignmentService(CourseAssignmentMapper courseAssignmentMapper) {
		this.courseAssignmentMapper = courseAssignmentMapper;
	}

	public List<CourseAssignment> findAll(
		Long teacherId,
		Long classGroupId,
		Long courseId,
		String status,
		Integer weekNumber
	) {
		validateOptionalId(teacherId, "教师ID必须大于0");
		validateOptionalId(classGroupId, "班级ID必须大于0");
		validateOptionalId(courseId, "课程ID必须大于0");
		validateOptionalWeekNumber(weekNumber);
		return courseAssignmentMapper.findAll(teacherId, classGroupId, courseId, normalizeStatus(status), weekNumber);
	}

	public List<CourseAssignmentView> findViews(
		Long teacherId,
		Long classGroupId,
		Long courseId,
		Integer weekNumber,
		Integer dayOfWeek,
		String status
	) {
		validateOptionalId(teacherId, "教师ID必须大于0");
		validateOptionalId(classGroupId, "班级ID必须大于0");
		validateOptionalId(courseId, "课程ID必须大于0");
		validateOptionalWeekNumber(weekNumber);
		validateOptionalDayOfWeek(dayOfWeek);
		return courseAssignmentMapper.findViews(
			teacherId,
			classGroupId,
			courseId,
			weekNumber,
			dayOfWeek,
			normalizeStatus(status)
		);
	}

	public List<CourseAssignmentView> findTeacherAssignments(Long teacherId, Integer weekNumber, Integer dayOfWeek) {
		Assert.positiveId(teacherId, "教师ID");
		return findViews(teacherId, null, null, weekNumber, dayOfWeek, null);
	}

	public List<CourseAssignmentView> findClassGroupAssignments(Long classGroupId, Integer weekNumber, Integer dayOfWeek) {
		Assert.positiveId(classGroupId, "班级ID");
		return findViews(null, classGroupId, null, weekNumber, dayOfWeek, null);
	}

	public CourseAssignment findById(Long id) {
		CourseAssignment assignment = courseAssignmentMapper.findById(id);
		if (assignment == null) {
			throw new ResourceNotFoundException("课程安排不存在");
		}
		return assignment;
	}

	public CourseAssignment create(CourseAssignmentRequest request) {
		CourseAssignment assignment = toAssignment(new CourseAssignment(), request);
		courseAssignmentMapper.insert(assignment);
		return findById(assignment.getId());
	}

	public CourseAssignment update(Long id, CourseAssignmentRequest request) {
		findById(id);
		CourseAssignment assignment = toAssignment(new CourseAssignment(), request);
		assignment.setId(id);
		courseAssignmentMapper.update(assignment);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		courseAssignmentMapper.cancel(id, AssignmentStatus.ACTIVE.code());
	}

	private CourseAssignment toAssignment(CourseAssignment assignment, CourseAssignmentRequest request) {
		validateOptionalId(request.sourceSchemeId(), "来源方案ID必须大于0");
		Assert.positiveId(request.teachingTaskId(), "教学任务ID");
		Assert.positiveId(request.classroomId(), "教室ID");
		Assert.positiveId(request.timeSlotId(), "时间段ID");
		assignment.setSourceSchemeId(request.sourceSchemeId());
		assignment.setTeachingTaskId(request.teachingTaskId());
		assignment.setClassroomId(request.classroomId());
		assignment.setTimeSlotId(request.timeSlotId());
		assignment.setStatus(StringUtils.hasText(request.status()) ? AssignmentStatus.from(request.status().trim()) : AssignmentStatus.ACTIVE);
		return assignment;
	}

	private void validateOptionalId(Long id, String message) {
		if (id != null && id <= 0) {
			throw new ValidationException(message);
		}
	}

	private void validateOptionalWeekNumber(Integer weekNumber) {
		if (weekNumber != null && (weekNumber < 1 || weekNumber > 18)) {
			throw new ValidationException("周次必须在1到18之间");
		}
	}

	private void validateOptionalDayOfWeek(Integer dayOfWeek) {
		if (dayOfWeek != null && (dayOfWeek < 1 || dayOfWeek > 7)) {
			throw new ValidationException("星期必须在1到7之间");
		}
	}

	private String normalizeStatus(String status) {
		return StringUtils.hasText(status) ? status.trim() : AssignmentStatus.ACTIVE.code();
	}
}
