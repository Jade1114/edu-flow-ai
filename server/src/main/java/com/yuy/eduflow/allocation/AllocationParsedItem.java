package com.yuy.eduflow.allocation;

public record AllocationParsedItem(
	Long teachingTaskId,
	Long timeSlotId,
	Long classroomId
) {
	public AllocationParsedItem(Long teachingTaskId, Long timeSlotId) {
		this(teachingTaskId, timeSlotId, null);
	}
}
