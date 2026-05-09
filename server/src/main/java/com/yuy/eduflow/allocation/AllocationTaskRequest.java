package com.yuy.eduflow.allocation;

public record AllocationTaskRequest(
	String name,
	String description,
	String priorityRule,
	String status,
	String createdBy
) {
}
