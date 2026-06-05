package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.ml.MlApiClient;
import com.yuy.eduflow.teacher.TeacherProfileSnapshotService;
import java.io.BufferedReader;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
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
	private final TeacherProfileSnapshotService teacherProfileSnapshotService;

	public AllocationMlSchemeService(
		AllocationTaskMapper allocationTaskMapper,
		AllocationSchemeMapper allocationSchemeMapper,
		ObjectMapper objectMapper,
		MlApiClient mlApiClient,
		TeacherProfileSnapshotService teacherProfileSnapshotService
	) {
		this.allocationTaskMapper = allocationTaskMapper;
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.objectMapper = objectMapper;
		this.mlApiClient = mlApiClient;
		this.teacherProfileSnapshotService = teacherProfileSnapshotService;
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
		progressReporter.accept(running("parse", "解析方案数据...", 68));
		List<AllocationParsedScheme> schemes;
		try {
			schemes = parseGeneratedSchemes(outputDir, taskId);
		} catch (IOException exception) {
			throw new BusinessException(500, "解析模型方案 JSONL 文件失败：" + exception.getMessage(), exception);
		}
		return new AllocationGenerationPreview(
			taskId,
			task.getName(),
			schemes
		);
	}

	/**
	 * Call Python FastAPI to generate schemes. Returns the output_dir from the response
	 * so the caller can read generated JSONL files.
	 */
	@SuppressWarnings("unchecked")
	private Path runModelScript(
		AllocationTask task,
		Consumer<GenerationStatus> progressReporter
	) {
		Map<String, Object> requestBody = new LinkedHashMap<>();
		requestBody.put("task_id", task.getId());
		Path teacherProfilesJsonl = teacherProfileSnapshotService.exportForAllocationTask(task.getId());
		if (teacherProfilesJsonl != null) {
			requestBody.put("teacher_profiles_jsonl", teacherProfilesJsonl.toString());
		} else {
			log.warn("教师画像不可用，排课将在无教师画像约束下进行：taskId={}", task.getId());
		}

		log.info("ML V3 scheme generator starting (HTTP): taskId={}, taskName={}",
			task.getId(), task.getName());

		progressReporter.accept(running("ml", "调用自训练排课模型生成候选方案...", 15));

		try {
			String outputDirStr = mlApiClient.generateSchemes(requestBody, progress -> {
				String stage = String.valueOf(progress.getOrDefault("stage", "ml"));
				String message = String.valueOf(progress.getOrDefault("message", "排课模型运行中..."));
				Integer progressValue = progress.get("progress") instanceof Number n ? n.intValue() : 20;
				progressReporter.accept(running(stage, message, progressValue));
			});
			if (outputDirStr == null || outputDirStr.isBlank()) {
				throw new BusinessException(500, "ML API 响应缺少 output_dir");
			}
			Path outputDir = Path.of(outputDirStr);
			log.info("ML scheme generator HTTP call succeeded: outputDir={}", outputDir);
			progressReporter.accept(running("ml", "自训练模型生成完成，准备入库...", 60));
			return outputDir;
		} catch (Exception e) {
			throw new BusinessException(500, "自训练模型 HTTP 调用失败：" + e.getMessage(), e);
		}
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

	private record SolverSummaryData(String rawJson, String teacherProfileAuditJson, Double qualityScore) {}

	private List<SolverSummaryData> loadSolverSummaries(Path outputDir) {
		Path jsonPath = outputDir.resolve("cp_sat_summary.json");
		if (!Files.exists(jsonPath)) {
			jsonPath = outputDir.resolve("ga_summary.json");
			if (!Files.exists(jsonPath)) {
				return List.of();
			}
		}
		try {
			String rawJson = Files.readString(jsonPath, StandardCharsets.UTF_8);
			List<SolverSummaryData> summaries = new ArrayList<>();
			@SuppressWarnings("unchecked")
			Map<String, Object> summaryMap = objectMapper.readValue(rawJson, Map.class);
			String teacherProfileAuditJson = extractJsonField(rawJson, "teacher_profile_audit");
			@SuppressWarnings("unchecked")
			List<Map<String, Object>> schemeSummaries = (List<Map<String, Object>>) summaryMap.getOrDefault("schemes", List.of());
			if (schemeSummaries.isEmpty()) {
				summaries.add(new SolverSummaryData(
					rawJson,
					teacherProfileAuditJson,
					summaryMap.get("quality_score") instanceof Number n ? n.doubleValue() : null
				));
				return summaries;
			}
			for (Map<String, Object> schemeSummary : schemeSummaries) {
				Double qualityScore = schemeSummary.get("quality_score") instanceof Number n ? n.doubleValue() : null;
				summaries.add(new SolverSummaryData(
					rawJson,
					teacherProfileAuditJson,
					qualityScore
				));
			}
			return summaries;
		} catch (IOException e) {
			log.warn("Failed to parse ML solver summary JSON {}: {}", jsonPath, e.getMessage());
			return List.of();
		}
	}

	private String mergeEvaluationSummary(EvaluationData evaluation, SolverSummaryData solverSummary) {
		String evaluationJson = evaluation != null ? cleanJsonObject(evaluation.evaluationSummary()) : null;
		if (solverSummary == null || solverSummary.rawJson() == null || solverSummary.rawJson().isBlank()) {
			return evaluationJson;
		}
		List<String> extraFields = new ArrayList<>();
		extraFields.add("\"solver_summary\":" + solverSummary.rawJson());
		if (solverSummary.teacherProfileAuditJson() != null) {
			extraFields.add("\"teacher_profile_audit\":" + solverSummary.teacherProfileAuditJson());
		}
		if (evaluationJson == null || evaluationJson.isBlank()) {
			return "{" + String.join(",", extraFields) + "}";
		}
		String body = evaluationJson.substring(1, evaluationJson.length() - 1).trim();
		return "{" + (body.isBlank() ? "" : body + ",") + String.join(",", extraFields) + "}";
	}

	private String cleanJsonObject(String rawJson) {
		if (rawJson == null || rawJson.isBlank()) {
			return null;
		}
		String trimmed = rawJson.trim();
		if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) {
			return null;
		}
		return trimmed;
	}

	private String extractJsonField(String rawJson, String fieldName) {
		String key = "\"" + fieldName + "\"";
		int keyIndex = rawJson.indexOf(key);
		if (keyIndex < 0) {
			return null;
		}
		int colonIndex = rawJson.indexOf(':', keyIndex + key.length());
		if (colonIndex < 0) {
			return null;
		}
		int valueStart = colonIndex + 1;
		while (valueStart < rawJson.length() && Character.isWhitespace(rawJson.charAt(valueStart))) {
			valueStart++;
		}
		if (valueStart >= rawJson.length()) {
			return null;
		}
		char opener = rawJson.charAt(valueStart);
		char closer = opener == '{' ? '}' : opener == '[' ? ']' : '\0';
		if (closer == '\0') {
			return null;
		}
		int valueEnd = findMatchingJsonEnd(rawJson, valueStart, opener, closer);
		return valueEnd > valueStart ? rawJson.substring(valueStart, valueEnd + 1) : null;
	}

	private int findMatchingJsonEnd(String rawJson, int start, char opener, char closer) {
		int depth = 0;
		boolean inString = false;
		boolean escaped = false;
		for (int i = start; i < rawJson.length(); i++) {
			char ch = rawJson.charAt(i);
			if (inString) {
				if (escaped) {
					escaped = false;
				} else if (ch == '\\') {
					escaped = true;
				} else if (ch == '"') {
					inString = false;
				}
				continue;
			}
			if (ch == '"') {
				inString = true;
			} else if (ch == opener) {
				depth++;
			} else if (ch == closer) {
				depth--;
				if (depth == 0) {
					return i;
				}
			}
		}
		return -1;
	}

	private List<AllocationParsedScheme> parseGeneratedSchemes(Path outputDir, Long taskId) throws IOException {
		Path schemesJsonl = outputDir.resolve("schemes.jsonl");
		if (!Files.exists(schemesJsonl)) {
			throw new ValidationException("自训练模型未生成 schemes.jsonl");
		}
		List<Map<String, Object>> schemesData = new ArrayList<>();
		for (String line : Files.readAllLines(schemesJsonl, StandardCharsets.UTF_8)) {
			if (line.isBlank()) continue;
			@SuppressWarnings("unchecked")
			Map<String, Object> scheme = objectMapper.readValue(line, Map.class);
			schemesData.add(scheme);
		}
		log.info("ML parsed schemes.jsonl: schemeCount={}", schemesData.size());
		List<SolverSummaryData> solverSummaries = loadSolverSummaries(outputDir);
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
				Number teacherProfileScore = (Number) itemData.get("teacher_profile_score");
				Number teacherProfilePenalty = (Number) itemData.get("teacher_profile_penalty");
				Object reasons = itemData.get("teacher_profile_reasons");
				Object components = itemData.get("teacher_profile_components");
				Object explanation = itemData.get("teacher_profile_penalty_explanation");
				items.add(new AllocationParsedItem(
					teachingTaskId != null ? teachingTaskId.longValue() : null,
					timeSlotId != null ? timeSlotId.longValue() : null,
					classroomId != null ? classroomId.longValue() : null,
					teacherProfileScore != null ? teacherProfileScore.doubleValue() : null,
					teacherProfilePenalty != null ? teacherProfilePenalty.doubleValue() : null,
					toJsonOrNull(reasons),
					toJsonOrNull(components),
					explanation instanceof String s && !s.isBlank() ? s : null
				));
			}
			String summary = buildSummary(items, itemsData);
			EvaluationData evaluation = loadEvaluation(outputDir, "scheme_" + String.format("%03d", i + 1));
			SolverSummaryData solverSummary = i < solverSummaries.size() ? solverSummaries.get(i) : null;
			String evaluationSummary = mergeEvaluationSummary(evaluation, solverSummary);
			String profileAudit = solverSummary != null ? solverSummary.teacherProfileAuditJson() : null;
			Double schemeScore = evaluation != null ? evaluation.schemeScore() : null;
			if (schemeScore == null && solverSummary != null) {
				schemeScore = solverSummary.qualityScore();
			}
			log.info("ML parsed scheme: index={}, itemCount={}, summary={}, evaluationScore={}, teacherProfileAudit={}",
				i + 1, items.size(), summary, schemeScore, profileAudit);
			int schemeIndex = existingMaxIndex + i + 1;
			schemes.add(new AllocationParsedScheme(
				"自训练模型方案 " + String.format("%03d", schemeIndex),
				summary,
				items,
				schemeScore,
				evaluationSummary,
				"v3"
			));
		}
		return schemes;
	}

	private String toJsonOrNull(Object value) {
		if (value == null) {
			return null;
		}
		try {
			return objectMapper.writeValueAsString(value);
		} catch (Exception e) {
			return null;
		}
	}

	private String buildSummary(List<AllocationParsedItem> items, List<Map<String, Object>> itemsData) {
		Map<Integer, Long> loadByDay = new LinkedHashMap<>();
		for (int day = 1; day <= 7; day++) {
			loadByDay.put(day, 0L);
		}
		BigDecimal totalRoomRankScore = BigDecimal.ZERO;
		int roomRankCount = 0;
		for (Map<String, Object> itemData : itemsData) {
			Object dayObj = itemData.get("day_of_week");
			if (dayObj instanceof Number dayNum) {
				int day = dayNum.intValue();
				loadByDay.computeIfPresent(day, (ignored, count) -> count + 1);
			}
			Object scoreObj = itemData.getOrDefault("room_rank_score", itemData.get("predicted_score"));
			if (scoreObj instanceof Number scoreNum) {
				totalRoomRankScore = totalRoomRankScore.add(BigDecimal.valueOf(scoreNum.doubleValue()));
				roomRankCount++;
			}
		}
		BigDecimal avgRoomRankScore = roomRankCount == 0
			? BigDecimal.ZERO
			: totalRoomRankScore.divide(BigDecimal.valueOf(roomRankCount), 4, java.math.RoundingMode.HALF_UP);
		return "片段 " + items.size() + "，平均教室排序分 " + avgRoomRankScore + "，星期分布 " + loadByDay;
	}

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}
}
