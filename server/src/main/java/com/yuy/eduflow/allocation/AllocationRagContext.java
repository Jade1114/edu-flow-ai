package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationRagContext(
	Long taskId,
	String taskName,
	String query,
	Integer topK,
	List<AllocationRagTeacherResult> teachers
) {
}
