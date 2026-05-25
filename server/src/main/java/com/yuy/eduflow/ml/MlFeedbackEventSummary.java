package com.yuy.eduflow.ml;

import java.util.List;
import java.util.Map;

public record MlFeedbackEventSummary(
	long eventCount,
	List<Map<String, Object>> eventTypes,
	List<Map<String, Object>> recentEvents
) {}
