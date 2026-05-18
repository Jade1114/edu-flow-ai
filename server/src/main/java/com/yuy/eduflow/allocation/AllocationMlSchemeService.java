package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.ml.MlApiClient;
import java.io.BufferedReader;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Service
public class AllocationMlSchemeService {

	private static final String DEFAULT_POLICY = "BALANCED";

	private final AllocationTaskMapper allocationTaskMapper;
	private final ObjectMapper objectMapper;
	private final MlApiClient mlApiClient;

	public AllocationMlSchemeService(
		AllocationTaskMapper allocationTaskMapper,
		ObjectMapper objectMapper,
		MlApiClient mlApiClient
	) {
		this.allocationTaskMapper = allocationTaskMapper;
		this.objectMapper = objectMapper;
		this.mlApiClient = mlApiClient;
	}

	public AllocationGenerationPreview generateSchemes(Long taskId, Consumer<GenerationStatus> progressReporter) {
		AllocationTask task = allocationTaskMapper.findById(taskId);
		if (task == null) {
			throw new ResourceNotFoundException("排课任务不存在");
		}
		List<AllocationTaskTeachingTaskResult> teachingTasks = allocationTaskMapper.findTeachingTasks(taskId);
		if (teachingTasks == null || teachingTasks.isEmpty()) {
			throw new ValidationException("排课任务未绑定教学任务，无法生成模型方案");
		}

		progressReporter.accept(running("ml", "调用自训练排课模型生成候选方案...", 15));
		// Python reads everything from DB and generates output_dir internally
		Path outputDir = runModelScript(task, progressReporter);
		progressReporter.accept(running("eval", "自训练模型评估方案质量...", 62));
		runEvaluator(outputDir);
		progressReporter.accept(running("parse", "解析评估后的 CSV 方案...", 68));
		String resolvedPolicy = policyOrDefault(null);
		List<AllocationParsedScheme> schemes;
		try {
			schemes = parseGeneratedSchemes(outputDir, resolvedPolicy);
		} catch (IOException exception) {
			throw new BusinessException(500, "解析模型方案 CSV 文件失败：" + exception.getMessage(), exception);
		}
		return new AllocationGenerationPreview(
			taskId,
			task.getName(),
			schemes
		);
	}

	/**
	 * Call Python FastAPI to generate schemes. Returns the output_dir from the response
	 * so the caller can read generated CSV files.
	 */
	@SuppressWarnings("unchecked")
	private Path runModelScript(
		AllocationTask task,
		Consumer<GenerationStatus> progressReporter
	) {
		Map<String, Object> requestBody = new LinkedHashMap<>();
		requestBody.put("task_id", task.getId());

		log.info("ML GA scheme generator starting (HTTP): taskId={}, taskName={}",
			task.getId(), task.getName());

		progressReporter.accept(running("ml", "调用自训练排课模型生成候选方案...", 15));

		try {
			Map<String, Object> response = mlApiClient.generateSchemes(requestBody);
			String outputDirStr = (String) response.get("output_dir");
			if (outputDirStr == null || outputDirStr.isBlank()) {
				throw new BusinessException(500, "ML API 响应缺少 output_dir");
			}
			Path outputDir = Path.of(outputDirStr);
			log.info("ML scheme generator HTTP call succeeded: outputDir={}, schemeCount={}, timingsMs={}",
				outputDir, response.get("scheme_count"), response.get("timings_ms"));
			progressReporter.accept(running("ml", "自训练模型生成完成，准备入库...", 60));
			return outputDir;
		} catch (Exception e) {
			throw new BusinessException(500, "自训练模型 HTTP 调用失败：" + e.getMessage(), e);
		}
	}

	private void runEvaluator(Path outputDir) {
		Path mlDir = resolveMlDir();
		List<String> command = new ArrayList<>();
		command.add(resolvePythonExecutable(mlDir));
		command.add("scripts/evaluate_scheme_demo.py");
		command.add("--scheme-dir");
		command.add(outputDir.toString());
		Path teacherPenalties = outputDir.resolve("teacher_penalties.json");
		if (Files.exists(teacherPenalties)) {
			command.add("--teacher-penalties");
			command.add(teacherPenalties.toString());
		}
		command.add("--json");

		ProcessBuilder builder = new ProcessBuilder(command);
		builder.directory(mlDir.toFile());
		builder.redirectErrorStream(true);
		log.info("ML scheme evaluator starting: dir={}, teacherPenalties={}", outputDir, Files.exists(teacherPenalties) ? teacherPenalties : "none");
		log.info("ML scheme evaluator command: {}", String.join(" ", command));

		try {
			Process process = builder.start();
			String output;
			try (BufferedReader reader = process.inputReader(StandardCharsets.UTF_8)) {
				output = reader.lines().collect(Collectors.joining("\n"));
			}
			int exitCode = process.waitFor();
			log.info("ML scheme evaluator done: exitCode={}", exitCode);
			if (!output.isBlank()) {
				log.info("ML scheme evaluator output:\n{}", output);
			}
			if (exitCode != 0) {
				log.warn("Scheme evaluator exited non-zero but continuing: {}", output);
			}
		} catch (IOException exception) {
			log.warn("Scheme evaluator failed: {}", exception.getMessage());
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			log.warn("Scheme evaluator interrupted");
		}
	}

	private Path resolveMlDir() {
		Path cwd = Path.of("").toAbsolutePath();
		Path direct = cwd.resolve("ml");
		if (Files.isDirectory(direct.resolve("scripts"))) {
			return direct;
		}
		Path nested = cwd.resolve("server/ml");
		if (Files.isDirectory(nested.resolve("scripts"))) {
			return nested;
		}
		throw new BusinessException(500, "未找到 server/ml 目录，无法调用自训练模型");
	}

	private String resolvePythonExecutable(Path mlDir) {
		Path venvPython = mlDir.resolve(".venv/bin/python");
		if (Files.isExecutable(venvPython)) {
			return venvPython.toString();
		}
		return "python3";
	}

	private record EvaluationData(Double schemeScore, String evaluationSummary) {}

	private EvaluationData loadEvaluation(Path outputDir, String schemeFileName) {
		String jsonFileName = schemeFileName.replace(".csv", ".json");
		Path jsonPath = outputDir.resolve(jsonFileName);
		if (!Files.exists(jsonPath)) {
			return null;
		}
		try {
			String rawJson = Files.readString(jsonPath, StandardCharsets.UTF_8);
			@SuppressWarnings("unchecked")
			Map<String, Object> evalMap = objectMapper.readValue(rawJson, Map.class);
			Object schemeScoreObj = evalMap.get("scheme_score");
			Double schemeScore = schemeScoreObj instanceof Number ? ((Number) schemeScoreObj).doubleValue() : null;
			return new EvaluationData(schemeScore, rawJson);
		} catch (IOException e) {
			log.warn("Failed to parse evaluation JSON {}: {}", jsonPath, e.getMessage());
			return null;
		}
	}

	private String policyOrDefault(String policy) {
		return policy != null && !policy.isBlank() ? policy : DEFAULT_POLICY;
	}

	private List<AllocationParsedScheme> parseGeneratedSchemes(Path outputDir, String policy) throws IOException {
		try (var stream = Files.list(outputDir)) {
			List<Path> schemeFiles = stream
				.filter(path -> path.getFileName().toString().matches("scheme_\\d+\\.csv"))
				.sorted(Comparator.comparing(path -> path.getFileName().toString()))
				.toList();
			if (schemeFiles.isEmpty()) {
				throw new ValidationException("自训练模型未生成任何方案 CSV");
			}
			log.info("ML generated scheme files discovered: outputDir={}, files={}", outputDir, schemeFiles.stream().map(path -> path.getFileName().toString()).toList());
			List<AllocationParsedScheme> schemes = new ArrayList<>();
			for (int i = 0; i < schemeFiles.size(); i++) {
				Path schemeFile = schemeFiles.get(i);
				List<AllocationParsedItem> items = parseSchemeItems(schemeFile);
				String summary = summarizeScheme(schemeFile, items);
				EvaluationData evaluation = loadEvaluation(outputDir, schemeFile.getFileName().toString());
				log.info("ML parsed scheme: file={}, itemCount={}, summary={}, evaluationScore={}", schemeFile.getFileName(), items.size(), summary, evaluation != null ? evaluation.schemeScore() : null);
				schemes.add(new AllocationParsedScheme(
					"自训练模型方案 " + String.format("%03d", i + 1),
					summary,
					items,
					evaluation != null ? evaluation.schemeScore() : null,
					evaluation != null ? evaluation.evaluationSummary() : null,
					policyOrDefault(policy),
					"v1"
				));
			}
			return schemes;
		}
	}

	private List<AllocationParsedItem> parseSchemeItems(Path schemeFile) throws IOException {
		List<String> lines = Files.readAllLines(schemeFile, StandardCharsets.UTF_8);
		if (lines.size() <= 1) {
			throw new ValidationException("模型方案为空：" + schemeFile.getFileName());
		}
		List<String> headers = parseCsvLine(lines.get(0));
		Map<String, Integer> headerIndex = new HashMap<>();
		for (int i = 0; i < headers.size(); i++) {
			headerIndex.put(headers.get(i), i);
		}
		List<AllocationParsedItem> items = new ArrayList<>();
		for (int i = 1; i < lines.size(); i++) {
			List<String> values = parseCsvLine(lines.get(i));
			items.add(new AllocationParsedItem(
				requireLong(values, headerIndex, "teaching_task_id", schemeFile),
				requireLong(values, headerIndex, "time_slot_id", schemeFile),
				requireLong(values, headerIndex, "classroom_id", schemeFile),
				optionalValue(values, headerIndex, "teacher_profile_penalty_explanation")
			));
		}
		return items;
	}

	private String summarizeScheme(Path schemeFile, List<AllocationParsedItem> items) throws IOException {
		Map<Integer, Long> loadByDay = new LinkedHashMap<>();
		for (int day = 1; day <= 7; day++) {
			loadByDay.put(day, 0L);
		}
		List<String> lines = Files.readAllLines(schemeFile, StandardCharsets.UTF_8);
		List<String> headers = parseCsvLine(lines.get(0));
		Map<String, Integer> headerIndex = new HashMap<>();
		for (int i = 0; i < headers.size(); i++) {
			headerIndex.put(headers.get(i), i);
		}
		BigDecimal totalPredictedScore = BigDecimal.ZERO;
		for (int i = 1; i < lines.size(); i++) {
			List<String> values = parseCsvLine(lines.get(i));
			Integer day = requireLong(values, headerIndex, "day_of_week", schemeFile).intValue();
			loadByDay.computeIfPresent(day, (ignored, count) -> count + 1);
			String predictedScore = requireValue(values, headerIndex, "predicted_score", schemeFile);
			totalPredictedScore = totalPredictedScore.add(new BigDecimal(predictedScore));
		}
		BigDecimal avgPredictedScore = items.isEmpty()
			? BigDecimal.ZERO
			: totalPredictedScore.divide(BigDecimal.valueOf(items.size()), 4, java.math.RoundingMode.HALF_UP);
		return "片段 " + items.size() + "，平均模型分 " + avgPredictedScore + "，星期分布 " + loadByDay;
	}

	private List<String> parseCsvLine(String line) {
		List<String> values = new ArrayList<>();
		StringBuilder current = new StringBuilder();
		boolean quoted = false;
		for (int i = 0; i < line.length(); i++) {
			char ch = line.charAt(i);
			if (ch == '"') {
				if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
					current.append('"');
					i++;
				} else {
					quoted = !quoted;
				}
			} else if (ch == ',' && !quoted) {
				values.add(current.toString());
				current.setLength(0);
			} else {
				current.append(ch);
			}
		}
		values.add(current.toString());
		return values;
	}

	private Long requireLong(List<String> values, Map<String, Integer> headerIndex, String fieldName, Path schemeFile) {
		return Long.valueOf(requireValue(values, headerIndex, fieldName, schemeFile));
	}

	private String requireValue(List<String> values, Map<String, Integer> headerIndex, String fieldName, Path schemeFile) {
		Integer index = headerIndex.get(fieldName);
		if (index == null || index >= values.size() || values.get(index).isBlank()) {
			throw new ValidationException("模型方案 " + schemeFile.getFileName() + " 缺少字段：" + fieldName);
		}
		return values.get(index).trim();
	}

	private String optionalValue(List<String> values, Map<String, Integer> headerIndex, String fieldName) {
		Integer index = headerIndex.get(fieldName);
		if (index == null || index >= values.size() || values.get(index).isBlank()) {
			return null;
		}
		return values.get(index).trim();
	}

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}
}
