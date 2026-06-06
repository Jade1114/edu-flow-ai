package com.yuy.eduflow.allocation;

public record AllocationItemRequest(
	Long schemeId,
	Long teachingTaskId,
	Long classroomId,
	Long timeSlotId,
	Boolean valid,
	String conflictMessage
) {
}
