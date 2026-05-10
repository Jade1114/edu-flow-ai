package com.yuy.eduflow.adjustment;

import java.util.List;

public record AdjustmentSuggestionPreview(
	Long requestId,
	Long assignmentId,
	String rawResponse,
	List<AdjustmentSuggestionCandidate> candidates,
	List<String> validationMessages
) {
}
