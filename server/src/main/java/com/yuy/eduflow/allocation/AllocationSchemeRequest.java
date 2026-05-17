package com.yuy.eduflow.allocation;

public record AllocationSchemeRequest(
	Long taskId,
	String schemeName,
	String summary,
	String satisfiedSummary,
	String conflictSummary,
	Boolean valid,
	String status
) {
}
