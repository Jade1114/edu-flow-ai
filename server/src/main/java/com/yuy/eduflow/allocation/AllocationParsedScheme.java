package com.yuy.eduflow.allocation;

import java.util.List;

public record AllocationParsedScheme(
	String schemeName,
	String summary,
	Integer score,
	String satisfiedSummary,
	List<AllocationParsedItem> items
) {
}
