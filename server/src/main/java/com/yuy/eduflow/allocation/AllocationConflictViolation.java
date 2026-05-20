package com.yuy.eduflow.allocation;

record AllocationConflictViolation(
	Long itemId,
	String conflictType,
	String message,
	Long relatedTeacherId,
	Long relatedClassGroupId,
	Long relatedClassroomId,
	Long relatedTimeSlotId,
	Long teachingTaskId,
	String courseName,
	Integer expectedHours,
	Integer actualHours
) {
}
