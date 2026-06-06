package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationParsedScheme(
	String schemeName,
	String summary,
	List<AllocationParsedItem> items,
	Double schemeScore,
	String evaluationSummary,
	String modelVersion
) {
	public AllocationParsedScheme(String schemeName, String summary, List<AllocationParsedItem> items) {
		this(schemeName, summary, items, null, null, null);
	}
}
