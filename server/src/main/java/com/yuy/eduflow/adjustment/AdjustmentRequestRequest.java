package com.yuy.eduflow.adjustment;

public record AdjustmentRequestRequest(
	Long assignmentId,
	Long teacherId,
	String reason,
	String preferredTimeText,
	Long preferredTimeSlotId,
	Long preferredClassroomId,
	String aiSuggestion,
	String status,
	String reviewNote
) {
}
