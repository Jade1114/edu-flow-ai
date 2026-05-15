package com.yuy.eduflow.allocation;

import java.util.List;

import java.util.Map;

public record AllocationParsedScheme(
	String schemeName,
	String summary,
	String satisfiedSummary,
	List<AllocationParsedItem> items,
	Double schemeScore,
	String evaluationSummary,
	String policy,
	String modelVersion
) {
	public AllocationParsedScheme(String schemeName, String summary, String satisfiedSummary, List<AllocationParsedItem> items) {
		this(schemeName, summary, satisfiedSummary, items, null, null, null, null);
	}
}
