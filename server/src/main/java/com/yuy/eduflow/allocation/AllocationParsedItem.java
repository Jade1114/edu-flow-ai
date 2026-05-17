package com.yuy.eduflow.allocation;

public record AllocationParsedItem(
	Long teachingTaskId,
	Long timeSlotId,
	Long classroomId,
	String conflictMessage
) {
	public AllocationParsedItem(Long teachingTaskId, Long timeSlotId) {
		this(teachingTaskId, timeSlotId, null, null);
	}

	public AllocationParsedItem(Long teachingTaskId, Long timeSlotId, Long classroomId) {
		this(teachingTaskId, timeSlotId, classroomId, null);
	}
}
