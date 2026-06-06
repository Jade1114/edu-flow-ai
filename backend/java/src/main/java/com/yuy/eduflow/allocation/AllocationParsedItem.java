package com.yuy.eduflow.allocation;

public record AllocationParsedItem(
	Long teachingTaskId,
	Long timeSlotId,
	Long classroomId,
	Double teacherProfileScore,
	Double teacherProfilePenalty,
	String teacherProfileReasonsJson,
	String teacherProfileComponentsJson,
	String conflictMessage
) {
	public AllocationParsedItem(Long teachingTaskId, Long timeSlotId) {
		this(teachingTaskId, timeSlotId, null, null, null, null, null, null);
	}

	public AllocationParsedItem(Long teachingTaskId, Long timeSlotId, Long classroomId) {
		this(teachingTaskId, timeSlotId, classroomId, null, null, null, null, null);
	}
}
