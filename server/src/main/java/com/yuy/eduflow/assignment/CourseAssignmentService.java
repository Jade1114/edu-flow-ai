package com.yuy.eduflow.assignment;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class CourseAssignmentService {
	private static final String DEFAULT_STATUS = "ACTIVE";

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
		if (weekNumber != null && (weekNumber < 1 || weekNumber > 18)) {
			throw new IllegalArgumentException("周次必须在1到18之间");
		}
		return courseAssignmentMapper.findAll(teacherId, classGroupId, courseId, status, weekNumber);
	}

	public CourseAssignment findById(Long id) {
		CourseAssignment assignment = courseAssignmentMapper.findById(id);
		if (assignment == null) {
			throw new IllegalArgumentException("课程安排不存在");
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
		courseAssignmentMapper.cancel(id);
	}

	private CourseAssignment toAssignment(CourseAssignment assignment, CourseAssignmentRequest request) {
		validateOptionalId(request.sourceSchemeId(), "来源方案ID必须大于0");
		requirePositiveId(request.courseId(), "课程ID不能为空");
		requirePositiveId(request.classGroupId(), "班级ID不能为空");
		requirePositiveId(request.teacherId(), "教师ID不能为空");
		requirePositiveId(request.classroomId(), "教室ID不能为空");
		requirePositiveId(request.timeSlotId(), "时间段ID不能为空");
		assignment.setSourceSchemeId(request.sourceSchemeId());
		assignment.setCourseId(request.courseId());
		assignment.setClassGroupId(request.classGroupId());
		assignment.setTeacherId(request.teacherId());
		assignment.setClassroomId(request.classroomId());
		assignment.setTimeSlotId(request.timeSlotId());
		assignment.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : DEFAULT_STATUS);
		return assignment;
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
}
