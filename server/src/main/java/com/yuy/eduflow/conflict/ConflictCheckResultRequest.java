package com.yuy.eduflow.conflict;

public record ConflictCheckResultRequest(
	String bizType,
	Long bizId,
	String conflictType,
	String message,
	Long relatedTeacherId,
	Long relatedClassGroupId,
	Long relatedClassroomId,
	Long relatedTimeSlotId,
	Boolean resolved
) {
}
