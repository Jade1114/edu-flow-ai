package com.yuy.eduflow.adjustment;

import java.util.List;

public record AdjustmentSuggestionSnapshot(
	List<AdjustmentSuggestionCandidate> candidates,
	List<String> validationMessages
) {
}
