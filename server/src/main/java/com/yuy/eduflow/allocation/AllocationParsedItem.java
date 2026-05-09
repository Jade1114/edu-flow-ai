package com.yuy.eduflow.allocation;

public record AllocationParsedItem(
	Long courseId,
	Long classGroupId,
	Long teacherId,
	Long classroomId,
	Long timeSlotId
) {
}
