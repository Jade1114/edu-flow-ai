package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationGenerateResult(
	Long taskId,
	int schemeCount,
	List<AllocationScheme> schemes
) {
}
