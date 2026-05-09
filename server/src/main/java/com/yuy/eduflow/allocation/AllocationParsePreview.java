package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationParsePreview(
	Long taskId,
	String taskName,
	String rawResponse,
	List<AllocationParsedScheme> schemes,
	List<String> validationMessages
) {
}
