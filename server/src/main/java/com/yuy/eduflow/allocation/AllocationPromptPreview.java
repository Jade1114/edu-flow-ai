package com.yuy.eduflow.allocation;

public record AllocationPromptPreview(
	Long taskId,
	String taskName,
	String systemPrompt,
	String userPrompt,
	String outputSchema,
	AllocationRagContext ragContext
) {
}
