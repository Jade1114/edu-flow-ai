package com.yuy.eduflow.allocation;

public record AllocationConfirmResult(
	Long schemeId,
	Long taskId,
	int assignmentCount,
	String schemeStatus,
	String taskStatus
) {
}
