package com.yuy.eduflow.adjustment;

public record AdjustmentSuggestionPromptPreview(
	Long requestId,
	Long assignmentId,
	String systemPrompt,
	String userPrompt,
	String outputSchema
) {
}
