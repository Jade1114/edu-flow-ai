package com.yuy.eduflow.allocation;

record AllocationConflictViolation(
	Long itemId,
	String conflictType,
	String message,
	Long relatedTeacherId,
	Long relatedClassGroupId,
	Long relatedClassroomId,
	Long relatedTimeSlotId
) {
}
