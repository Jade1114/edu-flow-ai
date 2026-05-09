package com.yuy.eduflow.allocation;

public record AllocationItemRequest(
	Long schemeId,
	Long courseId,
	Long classGroupId,
	Long teacherId,
	Long classroomId,
	Long timeSlotId,
	Boolean valid,
	String conflictMessage
) {
}
