package com.yuy.eduflow.rag;

public record VectorSearchRequest(
	String query,
	Integer topK,
	String status
) {
}
