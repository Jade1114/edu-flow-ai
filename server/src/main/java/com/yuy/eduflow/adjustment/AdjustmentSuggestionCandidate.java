package com.yuy.eduflow.adjustment;

public record AdjustmentSuggestionCandidate(
	Integer candidateIndex,
	String summary,
	Long newTimeSlotId,
	Long newClassroomId,
	Boolean valid,
	String conflictMessage
) {
	public AdjustmentSuggestionCandidate withConflictState(Boolean newValid, String newConflictMessage) {
		return new AdjustmentSuggestionCandidate(
			candidateIndex,
			summary,
			newTimeSlotId,
			newClassroomId,
			newValid,
			newConflictMessage
		);
	}
}
