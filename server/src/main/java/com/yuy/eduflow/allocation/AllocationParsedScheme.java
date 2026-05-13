package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationParsedScheme(
	String schemeName,
	String summary,
	String satisfiedSummary,
	List<AllocationParsedItem> items
) {
}
