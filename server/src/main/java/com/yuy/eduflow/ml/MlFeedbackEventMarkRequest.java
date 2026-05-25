package com.yuy.eduflow.ml;

public record MlFeedbackEventMarkRequest(
	String markType,
	String reasonCode,
	String reasonText
) {}
