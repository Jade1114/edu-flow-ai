package com.yuy.eduflow.allocation;

/**
 * Status of an async generation task.
 * Fields are exposed for JSON serialization.
 */
public class GenerationStatus {

	private String status; // RUNNING | COMPLETED | FAILED | IDLE
	private String stage;
	private String message;
	private Integer progress;
	private String error;
	private Integer schemeCount;
	private Long startedAt;
	private String solverStatus;
	private String summaryPath;
	private String outputDir;
	private String errorDiagnosis;
	private String stageStrategy;

	public GenerationStatus() {
	}

	public GenerationStatus(String status, String error, Integer schemeCount, Long startedAt) {
		this(status, null, null, null, error, schemeCount, startedAt);
	}

	public GenerationStatus(
		String status,
		String stage,
		String message,
		Integer progress,
		String error,
		Integer schemeCount,
		Long startedAt
	) {
		this.status = status;
		this.stage = stage;
		this.message = message;
		this.progress = progress;
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

	public String getStage() {
		return stage;
	}

	public void setStage(String stage) {
		this.stage = stage;
	}

	public String getMessage() {
		return message;
	}

	public void setMessage(String message) {
		this.message = message;
	}

	public Integer getProgress() {
		return progress;
	}

	public void setProgress(Integer progress) {
		this.progress = progress;
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

	public String getSolverStatus() {
		return solverStatus;
	}

	public void setSolverStatus(String solverStatus) {
		this.solverStatus = solverStatus;
	}

	public String getSummaryPath() {
		return summaryPath;
	}

	public void setSummaryPath(String summaryPath) {
		this.summaryPath = summaryPath;
	}

	public String getOutputDir() {
		return outputDir;
	}

	public void setOutputDir(String outputDir) {
		this.outputDir = outputDir;
	}

	public String getErrorDiagnosis() {
		return errorDiagnosis;
	}

	public void setErrorDiagnosis(String errorDiagnosis) {
		this.errorDiagnosis = errorDiagnosis;
	}

	public String getStageStrategy() {
		return stageStrategy;
	}

	public void setStageStrategy(String stageStrategy) {
		this.stageStrategy = stageStrategy;
	}
}
