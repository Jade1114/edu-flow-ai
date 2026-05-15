package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.io.BufferedReader;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
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

	private static final int DEFAULT_VARIANT_COUNT = 3;
	private static final int DEFAULT_TOP_K = 8;
	private static final int DEFAULT_CANDIDATE_POOL_SIZE = 500;
	private static final String DEFAULT_POLICY = "BALANCED";
	private static final DateTimeFormatter RUN_ID_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS");

	private final AllocationTaskMapper allocationTaskMapper;
	private final ObjectMapper objectMapper;

	public AllocationMlSchemeService(AllocationTaskMapper allocationTaskMapper, ObjectMapper objectMapper) {
		this.allocationTaskMapper = allocationTaskMapper;
		this.objectMapper = objectMapper;
	}

	public AllocationParsePreview generateParsePreview(Long taskId, Integer topK, String policy) {
		return generateParsePreview(taskId, topK, policy, ignored -> {});
	}

	public AllocationParsePreview generateParsePreview(Long taskId, Integer topK, String policy, Consumer<GenerationStatus> progressReporter) {
		AllocationTask task = allocationTaskMapper.findById(taskId);
		if (task == null) {
			throw new ResourceNotFoundException("排课任务不存在");
		}
		List<AllocationTaskTeachingTaskResult> teachingTasks = allocationTaskMapper.findTeachingTasks(taskId);
		if (teachingTasks == null || teachingTasks.isEmpty()) {
			throw new ValidationException("排课任务未绑定教学任务，无法生成模型方案");
		}

		progressReporter.accept(running("ml", "调用自训练排课模型生成候选方案...", 15));
		Path mlDir = resolveMlDir();
		Path outputDir = mlDir.resolve("data/generated_schemes/task_" + taskId + "_" + RUN_ID_FORMATTER.format(LocalDateTime.now()));
		List<String> teachingTaskIds = teachingTasks.stream()
			.map(result -> String.valueOf(result.getId()))
			.toList();

		try {
			Files.createDirectories(outputDir);
			runModelScript(mlDir, outputDir, task, teachingTaskIds, normalizedVariantCount(topK), progressReporter);
			progressReporter.accept(running("eval", "自训练模型评估方案质量...", 62));
			runEvaluator(mlDir, outputDir);
			progressReporter.accept(running("parse", "解析评估后的 CSV 方案...", 68));
			List<AllocationParsedScheme> schemes = parseGeneratedSchemes(outputDir);
			return new AllocationParsePreview(
				taskId,
				task.getName(),
				"Self-trained LightGBM schedule generation: " + outputDir,
				schemes,
				List.of()
			);
		} catch (IOException exception) {
			throw new BusinessException(500, "模型方案文件处理失败：" + exception.getMessage(), exception);
		}
	}

	private void runModelScript(
		Path mlDir,
		Path outputDir,
		AllocationTask task,
		List<String> teachingTaskIds,
		int variantCount,
		Consumer<GenerationStatus> progressReporter
	) {
		List<String> command = new ArrayList<>();
		command.add(resolvePythonExecutable(mlDir));
		command.add("scripts/generate_scheme_demo.py");
		command.add("--variant-count");
		command.add(String.valueOf(variantCount));
		command.add("--strategy");
		command.add("top-k-random");
		command.add("--top-k");
		command.add(String.valueOf(DEFAULT_TOP_K));
		command.add("--candidate-pool-size");
		command.add(String.valueOf(DEFAULT_CANDIDATE_POOL_SIZE));
		command.add("--policy");
		command.add(policyOrDefault(null));
		command.add("--teaching-task-ids");
		command.add(String.join(",", teachingTaskIds));
		command.add("--output-dir");
		command.add(outputDir.toString());
		command.add("--random-seed");
		command.add(String.valueOf(System.currentTimeMillis() % 1_000_000));
		if (task.getStartWeek() != null) {
			command.add("--start-week");
			command.add(String.valueOf(task.getStartWeek()));
		}
		if (task.getEndWeek() != null) {
			command.add("--end-week");
			command.add(String.valueOf(task.getEndWeek()));
		}

		ProcessBuilder builder = new ProcessBuilder(command);
		builder.directory(mlDir.toFile());
		builder.redirectErrorStream(true);
		log.info("Running ML scheme generator: {}", String.join(" ", command));

		try {
			Process process = builder.start();
			String output;
			try (BufferedReader reader = process.inputReader(StandardCharsets.UTF_8)) {
				output = reader.lines().collect(Collectors.joining("\n"));
			}
			int exitCode = process.waitFor();
			log.info("ML scheme generator exited with code={}, output={}", exitCode, output);
			if (exitCode != 0) {
				throw new BusinessException(500, "自训练模型生成失败：" + output);
			}
			progressReporter.accept(running("ml", "自训练模型生成完成，准备入库...", 60));
		} catch (IOException exception) {
			throw new BusinessException(500, "启动自训练模型脚本失败：" + exception.getMessage(), exception);
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new BusinessException(500, "自训练模型生成被中断", exception);
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

	private void runEvaluator(Path mlDir, Path outputDir) {
		List<String> command = new ArrayList<>();
		command.add(resolvePythonExecutable(mlDir));
		command.add("scripts/evaluate_scheme_demo.py");
		command.add("--scheme-dir");
		command.add(outputDir.toString());
		command.add("--json");

		ProcessBuilder builder = new ProcessBuilder(command);
		builder.directory(mlDir.toFile());
		builder.redirectErrorStream(true);
		log.info("Running ML scheme evaluator: {}", String.join(" ", command));

		try {
			Process process = builder.start();
			String output;
			try (BufferedReader reader = process.inputReader(StandardCharsets.UTF_8)) {
				output = reader.lines().collect(Collectors.joining("\n"));
			}
			int exitCode = process.waitFor();
			log.info("ML scheme evaluator exited with code={}, output={}", exitCode, output);
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

	private int normalizedVariantCount(Integer topK) {
		if (topK == null || topK <= 0) {
			return DEFAULT_VARIANT_COUNT;
		}
		return Math.min(Math.max(topK, 1), 5);
	}

	private List<AllocationParsedScheme> parseGeneratedSchemes(Path outputDir) throws IOException {
		try (var stream = Files.list(outputDir)) {
			List<Path> schemeFiles = stream
				.filter(path -> path.getFileName().toString().matches("scheme_\\d+\\.csv"))
				.sorted(Comparator.comparing(path -> path.getFileName().toString()))
				.toList();
			if (schemeFiles.isEmpty()) {
				throw new ValidationException("自训练模型未生成任何方案 CSV");
			}
			List<AllocationParsedScheme> schemes = new ArrayList<>();
			for (int i = 0; i < schemeFiles.size(); i++) {
				Path schemeFile = schemeFiles.get(i);
				List<AllocationParsedItem> items = parseSchemeItems(schemeFile);
				String summary = summarizeScheme(schemeFile, items);
				EvaluationData evaluation = loadEvaluation(outputDir, schemeFile.getFileName().toString());
				schemes.add(new AllocationParsedScheme(
					"自训练模型方案 " + String.format("%03d", i + 1),
					summary,
					"由 LightGBM 候选评分、规则预筛和方案状态惩罚共同生成",
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
				requireLong(values, headerIndex, "classroom_id", schemeFile)
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

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}
}
