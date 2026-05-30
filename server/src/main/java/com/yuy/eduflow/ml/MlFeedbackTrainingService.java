package com.yuy.eduflow.ml;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class MlFeedbackTrainingService {
	private static final Logger log = LoggerFactory.getLogger(MlFeedbackTrainingService.class);
	private static final DateTimeFormatter FILE_TIME_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

	private final MlFeedbackTrainingMapper mapper;
	private final tools.jackson.databind.ObjectMapper objectMapper;
	private final MlApiClient mlApiClient;
	private final AtomicReference<MlTrainingStatusResult> latestStatus = new AtomicReference<>(
		new MlTrainingStatusResult("IDLE", null, null, null, null, null, null, null, "No training started", null, null)
	);

	public MlFeedbackTrainingService(MlFeedbackTrainingMapper mapper, tools.jackson.databind.ObjectMapper objectMapper, MlApiClient mlApiClient) {
		this.mapper = mapper;
		this.objectMapper = objectMapper;
		this.mlApiClient = mlApiClient;
	}

	public MlFeedbackExportResult exportFeedback(Long taskId) {
		Path serverDir = resolveServerDir();
		Path exportDir = serverDir.resolve("ml/data/feedback/exports");
		String suffix = taskId == null ? "all" : "task_" + taskId;
		Path exportPath = exportDir.resolve("feedback_" + suffix + "_" + FILE_TIME_FORMAT.format(LocalDateTime.now()) + ".json");
		return exportFeedback(taskId, exportPath, null);
	}

	public MlFeedbackExportResult latestFeedbackExport(Long taskId) {
		Path serverDir = resolveServerDir();
		Path exportDir = serverDir.resolve("ml/data/feedback/exports");
		Path exportPath = latestFeedbackExportPath(exportDir, taskId);
		if (exportPath == null) {
			return null;
		}
		try {
			String json = Files.readString(exportPath);
			return new MlFeedbackExportResult(
				exportPath.toString(), null,
				countArray(json, "schemes"),
				countArray(json, "items"),
				countArray(json, "feedback"),
				countArray(json, "adjustments"),
				countArray(json, "conflicts"),
				countArray(json, "events")
			);
		} catch (IOException ex) {
			log.warn("Failed to read latest feedback export: {}", exportPath, ex);
			return null;
		}
	}

	public MlTrainingStatusResult train(Long taskId) {
		LocalDateTime startedAt = LocalDateTime.now();
		Path serverDir = resolveServerDir();
		Path dataDir = serverDir.resolve("ml/data");
		Path exportDir = dataDir.resolve("feedback/exports");
		Path sampleDir = dataDir.resolve("feedback/samples");
		String suffix = taskId == null ? "all" : "task_" + taskId;
		String time = FILE_TIME_FORMAT.format(startedAt);
		Path exportPath = latestFeedbackExportPath(exportDir, taskId);
		Path samplePath = sampleDir.resolve("feedback_samples_" + suffix + "_" + time + ".csv");
		Path activeModelPath = serverDir.resolve("ml/models/feedback/current/schedule_ranker.txt");
		Path activeSchemaPath = serverDir.resolve("ml/models/feedback/current/feature_schema.json");
		Path versionDir = serverDir.resolve("ml/models/feedback/archive").resolve(time);
		Path modelPath = versionDir.resolve("schedule_ranker.txt");
		Path schemaPath = versionDir.resolve("feature_schema.json");
		Path previousModelPath = Files.exists(activeModelPath)
			? activeModelPath
			: serverDir.resolve("ml/models/base/schedule_ranker_v1.txt");
		MlFeedbackExportResult exportStats = collectFeedbackStats(taskId, exportPath, samplePath);
		MlTrainingLog trainingLog = createRunningTrainingLog(startedAt, exportStats, modelPath, samplePath);
		mapper.insertTrainingLog(trainingLog);

		if (exportPath == null) {
			return finish(trainingLog, "FAILED", null, samplePath, modelPath, schemaPath,
				null, null, null, "请先手动生成反馈 JSON，再重训模型", startedAt);
		}

		latestStatus.set(new MlTrainingStatusResult(
			"RUNNING", exportPath.toString(), samplePath.toString(), modelPath.toString(), schemaPath.toString(),
			exportStats.schemeCount(), exportStats.feedbackCount(), null,
			"Building training samples from latest feedback JSON", startedAt, null
		));

		try {
			Map<String, Object> params = new LinkedHashMap<>();
			params.put("feedback_export_path", exportPath.toString());
			params.put("output_sample_path", samplePath.toString());
			params.put("output_model_path", modelPath.toString());
			params.put("output_schema_path", schemaPath.toString());

			Map<String, Object> result = mlApiClient.train(params);

			Integer sampleCount = result.get("sample_count") instanceof Number n ? n.intValue() : 0;
			Integer positiveCount = result.get("positive_count") instanceof Number n ? n.intValue() : 0;
			Integer negativeCount = result.get("negative_count") instanceof Number n ? n.intValue() : 0;
			trainingLog.setSampleCount(sampleCount);
			trainingLog.setPositiveCount(positiveCount);
			trainingLog.setNegativeCount(negativeCount);

			String metricsJson = readMetricsJson(schemaPath);
			trainingLog.setMetricsJson(metricsJson);
			extractValidationMetrics(trainingLog, metricsJson);

			appendTrainingComparison(schemaPath, previousModelPath, activeModelPath, modelPath);
			metricsJson = readMetricsJson(schemaPath);
			trainingLog.setMetricsJson(metricsJson);
			extractValidationMetrics(trainingLog, metricsJson);
			publishActiveModel(modelPath, activeModelPath, schemaPath, activeSchemaPath);

			return finish(trainingLog, "SUCCEEDED", exportPath, samplePath, modelPath, schemaPath,
				sampleCount, 0, 0, "Training completed successfully", startedAt);

		} catch (Exception ex) {
			return finish(trainingLog, "FAILED", exportPath, samplePath, modelPath, schemaPath,
				null, null, null, ex.getMessage(), startedAt);
		}
	}

	public MlTrainingStatusResult latestStatus() {
		return latestStatus.get();
	}

	public List<Map<String, Object>> getTrainingLogs(int limit) {
		return mapper.findTrainingLogs(limit);
	}

	public Map<String, Object> getLatestTrainingLog() {
		return mapper.findLatestTrainingLog();
	}

	private MlFeedbackExportResult exportFeedback(Long taskId, Path exportPath, Path samplePath) {
		log.debug("exportFeedback taskId={}, exportPath={}", taskId, exportPath);
		List<Map<String, Object>> schemes = mapper.findSchemes(taskId);
		List<Map<String, Object>> items = mapper.findItems(taskId);
		List<Map<String, Object>> feedback = mapper.findFeedback(taskId);
		List<Map<String, Object>> adjustments = mapper.findAdjustmentLogs(taskId);
		List<Map<String, Object>> conflicts = mapper.findConflicts(taskId);
		List<Map<String, Object>> events = mapper.findEvents(taskId);
		log.debug("exportFeedback done: schemes={}, items={}, feedback={}, adjustments={}, conflicts={}, events={}",
			schemes.size(), items.size(), feedback.size(), adjustments.size(), conflicts.size(), events.size());

		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("taskId", taskId);
		payload.put("exportedAt", LocalDateTime.now().toString());
		payload.put("schemes", schemes);
		payload.put("items", items);
		payload.put("feedback", feedback);
		payload.put("adjustments", adjustments);
		payload.put("conflicts", conflicts);
		payload.put("events", events);

		try {
			Files.createDirectories(exportPath.getParent());
			writeJson(exportPath, payload);
		} catch (IOException ex) {
			throw new IllegalStateException("Failed to export ML feedback data", ex);
		}

		return new MlFeedbackExportResult(
			exportPath.toString(), samplePath == null ? null : samplePath.toString(),
			schemes.size(), items.size(), feedback.size(), adjustments.size(), conflicts.size(), events.size()
		);
	}

	private int countArray(String json, String key) {
		String field = "\"" + key + "\"";
		int fieldIndex = json.indexOf(field);
		if (fieldIndex < 0) {
			return 0;
		}
		int arrayStart = json.indexOf('[', fieldIndex + field.length());
		if (arrayStart < 0) {
			return 0;
		}
		int depth = 0;
		int count = 0;
		boolean inString = false;
		boolean escaped = false;
		boolean itemStarted = false;
		for (int i = arrayStart; i < json.length(); i++) {
			char ch = json.charAt(i);
			if (escaped) {
				escaped = false;
				continue;
			}
			if (ch == '\\') {
				escaped = inString;
				continue;
			}
			if (ch == '"') {
				inString = !inString;
				continue;
			}
			if (inString) {
				continue;
			}
			if (ch == '[' || ch == '{') {
				depth++;
				if (depth == 2) {
					itemStarted = true;
				}
			} else if (ch == ']' || ch == '}') {
				if (depth == 2 && itemStarted) {
					count++;
					itemStarted = false;
				}
				depth--;
				if (depth == 0) {
					return count;
				}
			}
		}
		return count;
	}

	private MlFeedbackExportResult collectFeedbackStats(Long taskId, Path exportPath, Path samplePath) {
		List<Map<String, Object>> schemes = mapper.findSchemes(taskId);
		List<Map<String, Object>> items = mapper.findItems(taskId);
		List<Map<String, Object>> feedback = mapper.findFeedback(taskId);
		List<Map<String, Object>> adjustments = mapper.findAdjustmentLogs(taskId);
		List<Map<String, Object>> conflicts = mapper.findConflicts(taskId);
		List<Map<String, Object>> events = mapper.findEvents(taskId);
		return new MlFeedbackExportResult(
			exportPath == null ? null : exportPath.toString(),
			samplePath == null ? null : samplePath.toString(),
			schemes.size(), items.size(), feedback.size(), adjustments.size(), conflicts.size(), events.size()
		);
	}

	private MlTrainingLog createRunningTrainingLog(
		LocalDateTime startedAt,
		MlFeedbackExportResult exportStats,
		Path modelPath,
		Path samplePath
	) {
		MlTrainingLog trainingLog = new MlTrainingLog();
		trainingLog.setModelVersion("v" + FILE_TIME_FORMAT.format(startedAt));
		trainingLog.setTrainingType("FEEDBACK");
		trainingLog.setSchemeCount(exportStats.schemeCount());
		trainingLog.setItemCount(exportStats.itemCount());
		trainingLog.setFeedbackCount(exportStats.feedbackCount());
		trainingLog.setAdjustmentCount(exportStats.adjustmentCount());
		trainingLog.setConflictCount(exportStats.conflictCount());
		trainingLog.setModelPath(modelPath.toString());
		trainingLog.setSamplePath(samplePath.toString());
		trainingLog.setStatus("RUNNING");
		trainingLog.setTrainStartedAt(startedAt);
		return trainingLog;
	}

	private void appendTrainingComparison(Path schemaPath, Path previousModelPath, Path activeModelPath, Path newModelPath) {
		if (!Files.exists(schemaPath)) {
			return;
		}
		try {
			String json = Files.readString(schemaPath);
			String extraMetadata = ",\n  \"schema_path\": \"" + escapeJson(schemaPath.toString()) + "\"";
			String comparison = extraMetadata + ",\n  \"comparison\": {"
				+ "\n    \"previous_model_path\": \"" + escapeJson(previousModelPath.toString()) + "\","
				+ "\n    \"new_model_path\": \"" + escapeJson(newModelPath.toString()) + "\","
				+ "\n    \"active_model_path\": \"" + escapeJson(activeModelPath.toString()) + "\","
				+ "\n    \"baseline_type\": \"" + (Files.exists(activeModelPath) ? "PREVIOUS_FEEDBACK" : "INITIAL") + "\""
				+ "\n  }\n}";
			int end = json.lastIndexOf('}');
			if (end >= 0) {
				Files.writeString(schemaPath, json.substring(0, end) + comparison, StandardCharsets.UTF_8);
			}
		} catch (IOException ex) {
			log.warn("Failed to append training comparison metadata: {}", schemaPath, ex);
		}
	}

	private void publishActiveModel(Path modelPath, Path activeModelPath, Path schemaPath, Path activeSchemaPath) throws IOException {
		Files.createDirectories(activeModelPath.getParent());
		Files.createDirectories(activeSchemaPath.getParent());
		Files.copy(modelPath, activeModelPath, StandardCopyOption.REPLACE_EXISTING);
		Files.copy(schemaPath, activeSchemaPath, StandardCopyOption.REPLACE_EXISTING);
		log.info("Published feedback model: versionedModel={}, activeModel={}", modelPath, activeModelPath);
	}

	private String escapeJson(String value) {
		return value.replace("\\", "\\\\").replace("\"", "\\\"");
	}

	private String readMetricsJson(Path schemaPath) {
		if (!Files.exists(schemaPath)) {
			return null;
		}
		try {
			return Files.readString(schemaPath);
		} catch (IOException ex) {
			log.warn("Failed to read training metrics schema: {}", schemaPath, ex);
			return null;
		}
	}

	private void extractValidationMetrics(MlTrainingLog trainingLog, String metricsJson) {
		if (metricsJson == null) return;
		try {
			@SuppressWarnings("unchecked")
			Map<String, Object> schema = objectMapper.readValue(metricsJson, Map.class);
			@SuppressWarnings("unchecked")
			Map<String, Object> validation = (Map<String, Object>) schema.get("validation");
			if (validation == null) return;

			Number auc = (Number) validation.get("auc");
			if (auc != null) {
				trainingLog.setEvalAuc(auc.doubleValue());
			}
			Number scoreSeparation = (Number) validation.get("score_separation");
			if (scoreSeparation != null) {
				trainingLog.setEvalAccuracy(scoreSeparation.doubleValue());
			}
		} catch (Exception ex) {
			log.warn("Failed to extract validation metrics from schema", ex);
		}
	}

	private Path latestFeedbackExportPath(Path exportDir, Long taskId) {
		if (!Files.isDirectory(exportDir)) {
			return null;
		}
		String prefix = taskId == null ? "feedback_all_" : "feedback_task_" + taskId + "_";
		try (var stream = Files.list(exportDir)) {
			return stream
				.filter(path -> path.getFileName().toString().startsWith(prefix))
				.filter(path -> path.getFileName().toString().endsWith(".json"))
				.sorted((left, right) -> right.getFileName().toString().compareTo(left.getFileName().toString()))
				.findFirst()
				.orElse(null);
		} catch (IOException ex) {
			return null;
		}
	}

	private MlTrainingStatusResult finish(
		MlTrainingLog trainingLog,
		String status,
		Path exportPath,
		Path samplePath,
		Path modelPath,
		Path schemaPath,
		Integer sampleCount,
		Integer buildExitCode,
		Integer trainExitCode,
		String message,
		LocalDateTime startedAt
	) {
		LocalDateTime finishedAt = LocalDateTime.now();
		trainingLog.setStatus(status);
		trainingLog.setErrorMessage("SUCCEEDED".equals(status) ? null : message);
		trainingLog.setTrainFinishedAt(finishedAt);
		if (sampleCount != null) {
			trainingLog.setSampleCount(sampleCount);
		}
		mapper.updateTrainingLog(trainingLog);

		MlTrainingStatusResult result = new MlTrainingStatusResult(
			status,
			exportPath == null ? null : exportPath.toString(),
			samplePath == null ? null : samplePath.toString(),
			modelPath == null ? null : modelPath.toString(),
			schemaPath == null ? null : schemaPath.toString(),
			sampleCount,
			buildExitCode,
			trainExitCode,
			message,
			startedAt,
			finishedAt
		);
		latestStatus.set(result);
		return result;
	}

	private Path resolveServerDir() {
		Path cwd = Paths.get("").toAbsolutePath().normalize();
		if (Files.exists(cwd.resolve("pom.xml")) && Files.exists(cwd.resolve("ml"))) {
			return cwd;
		}
		if (Files.exists(cwd.resolve("server/pom.xml")) && Files.exists(cwd.resolve("ml"))) {
			return cwd;
		}
		return cwd;
	}

	private void writeJson(Path path, Object obj) throws IOException {
		StringBuilder sb = new StringBuilder();
		appendJson(sb, obj, 0);
		Files.writeString(path, sb.toString());
	}

	@SuppressWarnings("unchecked")
	private void appendJson(StringBuilder sb, Object obj, int indent) {
		String innerPad = "  ".repeat(indent + 1);
		if (obj == null) {
			sb.append("null");
		} else if (obj instanceof String s) {
			sb.append('"');
			for (char c : s.toCharArray()) {
				switch (c) {
					case '"' -> sb.append("\\\"");
					case '\\' -> sb.append("\\\\");
					case '\n' -> sb.append("\\n");
					case '\r' -> sb.append("\\r");
					case '\t' -> sb.append("\\t");
					default -> sb.append(c);
				}
			}
			sb.append('"');
		} else if (obj instanceof Number || obj instanceof Boolean) {
			sb.append(obj);
		} else if (obj instanceof Map<?, ?> m) {
			sb.append("{\n");
			int i = 0;
			for (var entry : m.entrySet()) {
				sb.append(innerPad);
				appendJson(sb, String.valueOf(entry.getKey()), indent + 1);
				sb.append(": ");
				appendJson(sb, entry.getValue(), indent + 1);
				if (++i < m.size()) sb.append(",");
				sb.append("\n");
			}
			sb.append("  ".repeat(indent)).append("}");
		} else if (obj instanceof List<?> list) {
			sb.append("[\n");
			for (int i = 0; i < list.size(); i++) {
				sb.append(innerPad);
				appendJson(sb, list.get(i), indent + 1);
				if (i < list.size() - 1) sb.append(",");
				sb.append("\n");
			}
			sb.append("  ".repeat(indent)).append("]");
		} else {
			appendJson(sb, String.valueOf(obj), indent);
		}
	}

	private record CommandResult(int exitCode, String output) {}
}
