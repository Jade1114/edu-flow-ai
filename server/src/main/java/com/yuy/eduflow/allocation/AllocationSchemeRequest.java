package com.yuy.eduflow.allocation;

public record AllocationSchemeRequest(
	Long taskId,
	String schemeName,
	String summary,
	String conflictSummary,
	Boolean valid,
	String status
) {
}
