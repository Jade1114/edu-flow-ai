package com.yuy.eduflow.allocation;

public record AllocationGeneratePreview(
	Long taskId,
	String taskName,
	String systemPrompt,
	String userPrompt,
	String outputSchema,
	String rawResponse
) {
}
