package com.yuy.eduflow.allocation;

/**
 * Status of an async generation task.
 * Fields are exposed for JSON serialization.
 */
public class GenerationStatus {

	private String status; // RUNNING | COMPLETED | FAILED | IDLE
	private String error;
	private Integer schemeCount;
	private Long startedAt;

	public GenerationStatus() {
	}

	public GenerationStatus(String status, String error, Integer schemeCount, Long startedAt) {
		this.status = status;
		this.error = error;
		this.schemeCount = schemeCount;
		this.startedAt = startedAt;
	}

	public String getStatus() {
		return status;
	}

	public void setStatus(String status) {
		this.status = status;
	}

	public String getError() {
		return error;
	}

	public void setError(String error) {
		this.error = error;
	}

	public Integer getSchemeCount() {
		return schemeCount;
	}

	public void setSchemeCount(Integer schemeCount) {
		this.schemeCount = schemeCount;
	}

	public Long getStartedAt() {
		return startedAt;
	}

	public void setStartedAt(Long startedAt) {
		this.startedAt = startedAt;
	}
}
