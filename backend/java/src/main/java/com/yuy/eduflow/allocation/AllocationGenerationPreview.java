package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationGenerationPreview(
	Long taskId,
	String taskName,
	List<AllocationParsedScheme> schemes
) {
}
