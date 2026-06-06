package com.yuy.eduflow.allocation;

public record BalancedStressTaskRequest(
	String name,
	Integer taskCount,
	Integer totalHours,
	String mode
) {
}
