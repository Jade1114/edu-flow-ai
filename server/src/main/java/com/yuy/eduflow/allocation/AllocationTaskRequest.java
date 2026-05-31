package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationTaskRequest(
	String name,
	String description,
	String status,
	String createdBy,
	List<Long> teachingTaskIds,
	AllocationTaskGenerationConfigRequest generationConfig
) {
}
