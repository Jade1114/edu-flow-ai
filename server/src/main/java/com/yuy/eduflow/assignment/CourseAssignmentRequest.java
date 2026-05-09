package com.yuy.eduflow.assignment;

public record CourseAssignmentRequest(
	Long sourceSchemeId,
	Long courseId,
	Long classGroupId,
	Long teacherId,
	Long classroomId,
	Long timeSlotId,
	String status
) {
}
