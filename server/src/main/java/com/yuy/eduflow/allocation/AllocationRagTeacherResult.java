package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.VectorSearchResult;
import java.util.Map;

public record AllocationRagTeacherResult(
	String id,
	Double score,
	Long teacherId,
	Long profileId,
	String teacherName,
	String department,
	String title,
	String status,
	String vectorText,
	Map<String, Object> payload
) {
	public static AllocationRagTeacherResult from(VectorSearchResult result) {
		return new AllocationRagTeacherResult(
			result.id(),
			result.score(),
			result.teacherId(),
			result.profileId(),
			result.teacherName(),
			result.department(),
			result.title(),
			result.status(),
			result.vectorText(),
			result.payload()
		);
	}
}
