package com.yuy.eduflow.adjustment;

public record AdjustmentConfirmResult(
	Long requestId,
	Long assignmentId,
	Integer candidateIndex,
	Long newTimeSlotId,
	Long newClassroomId,
	String status,
	String reviewNote
) {
}
