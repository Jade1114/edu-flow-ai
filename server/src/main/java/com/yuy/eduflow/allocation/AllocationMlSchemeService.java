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

	private final AllocationTaskMapper allocationTaskMapper;
	private final AllocationSchemeMapper allocationSchemeMapper;
	private final ObjectMapper objectMapper;
	private final MlApiClient mlApiClient;

	public AllocationMlSchemeService(
		AllocationTaskMapper allocationTaskMapper,
		AllocationSchemeMapper allocationSchemeMapper,
		ObjectMapper objectMapper,
		MlApiClient mlApiClient
	) {
		this.allocationTaskMapper = allocationTaskMapper;
		this.allocationSchemeMapper = allocationSchemeMapper;
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
		List<AllocationParsedScheme> schemes;
		try {
			schemes = parseGeneratedSchemes(outputDir, taskId);
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
		// 从项目根目录启动：cwd/ml/
		Path direct = cwd.resolve("ml");
		if (Files.isDirectory(direct.resolve("scripts"))) {
			return direct;
		}
		// 从 server/ 目录启动：cwd/../ml/
		Path parent = cwd.resolve("../ml").normalize();
		if (Files.isDirectory(parent.resolve("scripts"))) {
			return parent;
		}
		throw new BusinessException(500, "未找到 ml/ 目录（已从 server/ml/ 迁移），无法调用自训练模型");
	}

	private String resolvePythonExecutable(Path mlDir) {
		Path venvPython = mlDir.resolve(".venv/bin/python");
		if (Files.isExecutable(venvPython)) {
			return venvPython.toString();
		}
		return "python3";
	}

	private record EvaluationData(Double schemeScore, String evaluationSummary) {}

	private EvaluationData loadEvaluation(Path outputDir, String schemeBaseName) {
		Path jsonPath = outputDir.resolve(schemeBaseName + ".json");
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

	private List<AllocationParsedScheme> parseGeneratedSchemes(Path outputDir, Long taskId) throws IOException {
		Path schemesJson = outputDir.resolve("schemes.json");
		if (!Files.exists(schemesJson)) {
			throw new ValidationException("自训练模型未生成 schemes.json");
		}
		String rawJson = Files.readString(schemesJson, StandardCharsets.UTF_8);
		@SuppressWarnings("unchecked")
		List<Map<String, Object>> schemesData = objectMapper.readValue(rawJson, List.class);
		log.info("ML parsed schemes.json: schemeCount={}", schemesData.size());
		int existingMaxIndex = allocationSchemeMapper.selectMaxSchemeIndex(taskId);
		log.info("Existing max scheme index for taskId={}: {}", taskId, existingMaxIndex);
		List<AllocationParsedScheme> schemes = new ArrayList<>();
		for (int i = 0; i < schemesData.size(); i++) {
			Map<String, Object> schemeData = schemesData.get(i);
			@SuppressWarnings("unchecked")
			List<Map<String, Object>> itemsData = (List<Map<String, Object>>) schemeData.getOrDefault("items", List.of());
			List<AllocationParsedItem> items = new ArrayList<>();
			for (Map<String, Object> itemData : itemsData) {
				Number teachingTaskId = (Number) itemData.get("teaching_task_id");
				Number timeSlotId = (Number) itemData.get("time_slot_id");
				Number classroomId = (Number) itemData.get("classroom_id");
				Object explanation = itemData.get("teacher_profile_penalty_explanation");
				items.add(new AllocationParsedItem(
					teachingTaskId != null ? teachingTaskId.longValue() : null,
					timeSlotId != null ? timeSlotId.longValue() : null,
					classroomId != null ? classroomId.longValue() : null,
					explanation instanceof String s && !s.isBlank() ? s : null
				));
			}
			String summary = buildSummary(items, itemsData);
			EvaluationData evaluation = loadEvaluation(outputDir, "scheme_" + String.format("%03d", i + 1));
			log.info("ML parsed scheme: index={}, itemCount={}, summary={}, evaluationScore={}", i + 1, items.size(), summary, evaluation != null ? evaluation.schemeScore() : null);
			int schemeIndex = existingMaxIndex + i + 1;
			schemes.add(new AllocationParsedScheme(
				"自训练模型方案 " + String.format("%03d", schemeIndex),
				summary,
				items,
				evaluation != null ? evaluation.schemeScore() : null,
				evaluation != null ? evaluation.evaluationSummary() : null,
				"v1"
			));
		}
		return schemes;
	}

	private String buildSummary(List<AllocationParsedItem> items, List<Map<String, Object>> itemsData) {
		Map<Integer, Long> loadByDay = new LinkedHashMap<>();
		for (int day = 1; day <= 7; day++) {
			loadByDay.put(day, 0L);
		}
		BigDecimal totalPredictedScore = BigDecimal.ZERO;
		int dayPredictCount = 0;
		for (Map<String, Object> itemData : itemsData) {
			Object dayObj = itemData.get("day_of_week");
			if (dayObj instanceof Number dayNum) {
				int day = dayNum.intValue();
				loadByDay.computeIfPresent(day, (ignored, count) -> count + 1);
			}
			Object scoreObj = itemData.get("predicted_score");
			if (scoreObj instanceof Number scoreNum) {
				totalPredictedScore = totalPredictedScore.add(BigDecimal.valueOf(scoreNum.doubleValue()));
				dayPredictCount++;
			}
		}
		BigDecimal avgPredictedScore = dayPredictCount == 0
			? BigDecimal.ZERO
			: totalPredictedScore.divide(BigDecimal.valueOf(dayPredictCount), 4, java.math.RoundingMode.HALF_UP);
		return "片段 " + items.size() + "，平均模型分 " + avgPredictedScore + "，星期分布 " + loadByDay;
	}

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}
}
