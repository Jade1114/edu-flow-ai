package com.yuy.eduflow.ml;

public record MlFeedbackExportResult(
	String exportPath,
	String samplePath,
	int schemeCount,
	int itemCount,
	int feedbackCount,
	int adjustmentCount,
	int conflictCount,
	int eventCount
) {}
