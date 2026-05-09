package com.yuy.eduflow.rag;

import java.util.Map;

public record VectorSearchResult(
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
}
