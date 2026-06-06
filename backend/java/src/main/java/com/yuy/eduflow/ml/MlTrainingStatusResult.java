package com.yuy.eduflow.ml;

import java.time.LocalDateTime;

public record MlTrainingStatusResult(
	String status,
	String exportPath,
	String samplePath,
	String modelPath,
	String schemaPath,
	Integer sampleCount,
	Integer buildExitCode,
	Integer trainExitCode,
	String message,
	LocalDateTime startedAt,
	LocalDateTime finishedAt
) {}
