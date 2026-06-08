package com.yuy.eduflow.allocation;

public record V35TemplateGenerationStatus(
	String status,       // IDLE | RUNNING | SUCCESS | FAILED
	Long startedAt,
	Integer progress,
	String error
) {
	public V35TemplateGenerationStatus(String status, Long startedAt, Integer progress) {
		this(status, startedAt, progress, null);
	}
}
