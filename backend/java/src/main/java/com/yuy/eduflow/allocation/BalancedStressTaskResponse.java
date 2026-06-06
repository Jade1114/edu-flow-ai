package com.yuy.eduflow.allocation;

import java.util.Map;

public record BalancedStressTaskResponse(
	Long allocationTaskId,
	AllocationTaskGenerationConfig generationConfig,
	Map<String, Object> distributionSummary,
	Integer insertedTeachingTaskCount
) {
}
