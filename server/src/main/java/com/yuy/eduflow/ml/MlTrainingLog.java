package com.yuy.eduflow.ml;

import java.time.LocalDateTime;

public class MlTrainingLog {
	private Long id;
	private String modelVersion;
	private String trainingType;
	private int schemeCount;
	private int itemCount;
	private int feedbackCount;
	private int adjustmentCount;
	private int conflictCount;
	private int sampleCount;
	private int positiveCount;
	private int negativeCount;
	private Double trainAccuracy;
	private Double trainAuc;
	private Double evalAccuracy;
	private Double evalAuc;
	private String modelPath;
	private String samplePath;
	private String metricsJson;
	private String status;
	private String errorMessage;
	private LocalDateTime trainStartedAt;
	private LocalDateTime trainFinishedAt;

	public Long getId() {
		return id;
	}

	public void setId(Long id) {
		this.id = id;
	}

	public String getModelVersion() {
		return modelVersion;
	}

	public void setModelVersion(String modelVersion) {
		this.modelVersion = modelVersion;
	}

	public String getTrainingType() {
		return trainingType;
	}

	public void setTrainingType(String trainingType) {
		this.trainingType = trainingType;
	}

	public int getSchemeCount() {
		return schemeCount;
	}

	public void setSchemeCount(int schemeCount) {
		this.schemeCount = schemeCount;
	}

	public int getItemCount() {
		return itemCount;
	}

	public void setItemCount(int itemCount) {
		this.itemCount = itemCount;
	}

	public int getFeedbackCount() {
		return feedbackCount;
	}

	public void setFeedbackCount(int feedbackCount) {
		this.feedbackCount = feedbackCount;
	}

	public int getAdjustmentCount() {
		return adjustmentCount;
	}

	public void setAdjustmentCount(int adjustmentCount) {
		this.adjustmentCount = adjustmentCount;
	}

	public int getConflictCount() {
		return conflictCount;
	}

	public void setConflictCount(int conflictCount) {
		this.conflictCount = conflictCount;
	}

	public int getSampleCount() {
		return sampleCount;
	}

	public void setSampleCount(int sampleCount) {
		this.sampleCount = sampleCount;
	}

	public int getPositiveCount() {
		return positiveCount;
	}

	public void setPositiveCount(int positiveCount) {
		this.positiveCount = positiveCount;
	}

	public int getNegativeCount() {
		return negativeCount;
	}

	public void setNegativeCount(int negativeCount) {
		this.negativeCount = negativeCount;
	}

	public Double getTrainAccuracy() {
		return trainAccuracy;
	}

	public void setTrainAccuracy(Double trainAccuracy) {
		this.trainAccuracy = trainAccuracy;
	}

	public Double getTrainAuc() {
		return trainAuc;
	}

	public void setTrainAuc(Double trainAuc) {
		this.trainAuc = trainAuc;
	}

	public Double getEvalAccuracy() {
		return evalAccuracy;
	}

	public void setEvalAccuracy(Double evalAccuracy) {
		this.evalAccuracy = evalAccuracy;
	}

	public Double getEvalAuc() {
		return evalAuc;
	}

	public void setEvalAuc(Double evalAuc) {
		this.evalAuc = evalAuc;
	}

	public String getModelPath() {
		return modelPath;
	}

	public void setModelPath(String modelPath) {
		this.modelPath = modelPath;
	}

	public String getSamplePath() {
		return samplePath;
	}

	public void setSamplePath(String samplePath) {
		this.samplePath = samplePath;
	}

	public String getMetricsJson() {
		return metricsJson;
	}

	public void setMetricsJson(String metricsJson) {
		this.metricsJson = metricsJson;
	}

	public String getStatus() {
		return status;
	}

	public void setStatus(String status) {
		this.status = status;
	}

	public String getErrorMessage() {
		return errorMessage;
	}

	public void setErrorMessage(String errorMessage) {
		this.errorMessage = errorMessage;
	}

	public LocalDateTime getTrainStartedAt() {
		return trainStartedAt;
	}

	public void setTrainStartedAt(LocalDateTime trainStartedAt) {
		this.trainStartedAt = trainStartedAt;
	}

	public LocalDateTime getTrainFinishedAt() {
		return trainFinishedAt;
	}

	public void setTrainFinishedAt(LocalDateTime trainFinishedAt) {
		this.trainFinishedAt = trainFinishedAt;
	}
}
