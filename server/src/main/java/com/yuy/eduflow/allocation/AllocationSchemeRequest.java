package com.yuy.eduflow.allocation;

public record AllocationSchemeRequest(
	Long taskId,
	String schemeName,
	String summary,
	Integer score,
	String satisfiedSummary,
	String conflictSummary,
	Boolean valid,
	String status
) {
}
