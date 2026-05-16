package com.yuy.eduflow.ml;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
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
	private final AtomicReference<MlTrainingStatusResult> latestStatus = new AtomicReference<>(
		new MlTrainingStatusResult("IDLE", null, null, null, null, null, null, null, "No training started", null, null)
	);

	public MlFeedbackTrainingService(MlFeedbackTrainingMapper mapper) {
		this.mapper = mapper;
	}

	public MlFeedbackExportResult exportFeedback(Long taskId) {
		try {
			Path serverDir = resolveServerDir();
			Path exportDir = serverDir.resolve("ml/data/feedback_exports");
			String suffix = taskId == null ? "all" : "task_" + taskId;
			Path exportPath = exportDir.resolve("feedback_" + suffix + "_" + FILE_TIME_FORMAT.format(LocalDateTime.now()) + ".json");
			return exportFeedback(taskId, exportPath, null);
		} catch (Exception e) {
			log.error("exportFeedback failed: {}", e.getMessage(), e);
			throw e;
		}
	}

	public MlTrainingStatusResult train(Long taskId) {
		LocalDateTime startedAt = LocalDateTime.now();
		Path serverDir = resolveServerDir();
		Path dataDir = serverDir.resolve("ml/data");
		Path exportDir = dataDir.resolve("feedback_exports");
		String suffix = taskId == null ? "all" : "task_" + taskId;
		String time = FILE_TIME_FORMAT.format(startedAt);
		Path exportPath = exportDir.resolve("feedback_" + suffix + "_" + time + ".json");
		Path samplePath = dataDir.resolve("feedback_training_samples_" + suffix + "_" + time + ".csv");
		Path modelPath = serverDir.resolve("ml/models/schedule_ranker_feedback.txt");
		Path schemaPath = dataDir.resolve("feedback_feature_schema.json");

		latestStatus.set(new MlTrainingStatusResult(
			"RUNNING", exportPath.toString(), samplePath.toString(), modelPath.toString(), schemaPath.toString(),
			null, null, null, "Exporting feedback data", startedAt, null
		));

		try {
			MlFeedbackExportResult exportResult = exportFeedback(taskId, exportPath, samplePath);

			latestStatus.set(new MlTrainingStatusResult(
				"RUNNING", exportPath.toString(), samplePath.toString(), modelPath.toString(), schemaPath.toString(),
				exportResult.schemeCount(), exportResult.feedbackCount(), null, "Building training samples",
				startedAt, null
			));

			Path scriptsDir = serverDir.resolve("ml/scripts");
			Path pythonExe = resolvePythonExecutable(serverDir);

			CommandResult buildResult = runCommand(scriptsDir, pythonExe.toString(),
				"build_feedback_training_samples.py",
				"--input", exportPath.toString(),
				"--output", samplePath.toString()
			);

			int sampleCount = countCsvSamples(samplePath);

			if (buildResult.exitCode() != 0) {
				return finish("FAILED", exportPath, samplePath, modelPath, schemaPath,
					sampleCount, buildResult.exitCode(), null,
					"Sample build failed: " + buildResult.output(), startedAt);
			}

			latestStatus.set(new MlTrainingStatusResult(
				"RUNNING", exportPath.toString(), samplePath.toString(), modelPath.toString(), schemaPath.toString(),
				exportResult.schemeCount(), exportResult.feedbackCount(), sampleCount, "Training LightGBM model",
				startedAt, null
			));

			CommandResult trainResult = runCommand(scriptsDir, pythonExe.toString(),
				"train_lightgbm.py",
				"--input", samplePath.toString(),
				"--output", modelPath.toString(),
				"--schema-output", schemaPath.toString()
			);

			if (trainResult.exitCode() != 0) {
				return finish("FAILED", exportPath, samplePath, modelPath, schemaPath,
					sampleCount, buildResult.exitCode(), trainResult.exitCode(),
					"Train failed: " + trainResult.output(), startedAt);
			}

			return finish("SUCCEEDED", exportPath, samplePath, modelPath, schemaPath,
				sampleCount, buildResult.exitCode(), trainResult.exitCode(),
				"Training completed successfully", startedAt);

		} catch (Exception ex) {
			return finish("FAILED", exportPath, samplePath, modelPath, schemaPath,
				null, null, null, ex.getMessage(), startedAt);
		}
	}

	public MlTrainingStatusResult latestStatus() {
		return latestStatus.get();
	}

	public List<Map<String, Object>> getTrainingLogs(int limit) {
		try {
			return mapper.findTrainingLogs(limit);
		} catch (Exception e) {
			log.error("getTrainingLogs failed: {}", e.getMessage(), e);
			throw e;
		}
	}

	public Map<String, Object> getLatestTrainingLog() {
		try {
			return mapper.findLatestTrainingLog();
		} catch (Exception e) {
			log.error("getLatestTrainingLog failed: {}", e.getMessage(), e);
			throw e;
		}
	}

	private MlFeedbackExportResult exportFeedback(Long taskId, Path exportPath, Path samplePath) {
		log.info("exportFeedback taskId={}, exportPath={}", taskId, exportPath);
		List<Map<String, Object>> schemes = mapper.findSchemes(taskId);
		log.info("  schemes: {} rows", schemes.size());
		List<Map<String, Object>> items = mapper.findItems(taskId);
		log.info("  items: {} rows", items.size());
		List<Map<String, Object>> feedback = mapper.findFeedback(taskId);
		log.info("  feedback: {} rows", feedback.size());
		List<Map<String, Object>> adjustments = mapper.findAdjustmentLogs(taskId);
		log.info("  adjustments: {} rows", adjustments.size());
		List<Map<String, Object>> conflicts = mapper.findConflicts(taskId);
		log.info("  conflicts: {} rows", conflicts.size());

		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("taskId", taskId);
		payload.put("exportedAt", LocalDateTime.now().toString());
		payload.put("schemes", schemes);
		payload.put("items", items);
		payload.put("feedback", feedback);
		payload.put("adjustments", adjustments);
		payload.put("conflicts", conflicts);

		try {
			Files.createDirectories(exportPath.getParent());
			writeJson(exportPath, payload);
		} catch (IOException ex) {
			throw new IllegalStateException("Failed to export ML feedback data", ex);
		}

		return new MlFeedbackExportResult(
			exportPath.toString(), samplePath == null ? null : samplePath.toString(),
			schemes.size(), items.size(), feedback.size(), adjustments.size(), conflicts.size(), 0
		);
	}

	private MlTrainingStatusResult finish(
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
			LocalDateTime.now()
		);
		latestStatus.set(result);
		return result;
	}

	private CommandResult runCommand(Path workingDir, String... command) throws IOException, InterruptedException {
		Process process = new ProcessBuilder(command)
			.directory(workingDir.toFile())
			.redirectErrorStream(true)
			.start();
		StringBuilder output = new StringBuilder();
		try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
			String line;
			while ((line = reader.readLine()) != null) {
				output.append(line).append(System.lineSeparator());
			}
		}
		return new CommandResult(process.waitFor(), output.toString().trim());
	}

	private int countCsvSamples(Path samplePath) throws IOException {
		if (!Files.exists(samplePath)) {
			return 0;
		}
		try (var lines = Files.lines(samplePath)) {
			return (int) Math.max(0, lines.count() - 1);
		}
	}

	private Path resolveServerDir() {
		Path cwd = Paths.get("").toAbsolutePath().normalize();
		if (Files.exists(cwd.resolve("pom.xml")) && Files.exists(cwd.resolve("ml"))) {
			return cwd;
		}
		if (Files.exists(cwd.resolve("server/pom.xml")) && Files.exists(cwd.resolve("server/ml"))) {
			return cwd.resolve("server");
		}
		return cwd;
	}

	private Path resolvePythonExecutable(Path serverDir) {
		Path venvPython = serverDir.resolve("ml/.venv/bin/python");
		if (Files.exists(venvPython)) {
			return venvPython;
		}
		return Paths.get("python3");
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
