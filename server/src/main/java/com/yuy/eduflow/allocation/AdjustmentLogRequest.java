package com.yuy.eduflow.allocation;

public record AdjustmentLogRequest(
	Long itemId,
	Long teachingTaskId,
	Long fromTimeSlotId,
	Long toTimeSlotId,
	Long fromClassroomId,
	Long toClassroomId,
	String reason
) {
}
