package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.teachingtask.TeachingTaskMapper;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Service
public class AllocationGenerateParseService {
	private static final Pattern CODE_FENCE_PATTERN = Pattern.compile(
		"```\\s*(?:json)?\\s*([\\s\\S]*?)```",
		Pattern.CASE_INSENSITIVE
	);

	private final AllocationGeneratePreviewService allocationGeneratePreviewService;
	private final TeachingTaskMapper teachingTaskMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;
	private final ObjectMapper objectMapper;

	public AllocationGenerateParseService(
		AllocationGeneratePreviewService allocationGeneratePreviewService,
		TeachingTaskMapper teachingTaskMapper,
		AllocationTaskMapper allocationTaskMapper,
		ClassroomService classroomService,
		TimeSlotService timeSlotService,
		ObjectMapper objectMapper
	) {
		this.allocationGeneratePreviewService = allocationGeneratePreviewService;
		this.teachingTaskMapper = teachingTaskMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
		this.objectMapper = objectMapper;
	}

	public AllocationParsePreview generateParsePreview(Long taskId, Integer topK) {
		return generateParsePreview(taskId, topK, ignored -> {});
	}

	public AllocationParsePreview generateParsePreview(Long taskId, Integer topK, Consumer<GenerationStatus> progressReporter) {
		log.info("=== ParseService generateParsePreview() start === taskId={}, topK={}", taskId, topK);
		long t0 = System.currentTimeMillis();
		AllocationGeneratePreview generatePreview = allocationGeneratePreviewService.generate(taskId, topK, progressReporter);
		log.info("[{}ms] LLM + parse done, raw response length={}chars", System.currentTimeMillis() - t0, generatePreview.rawResponse().length());
		String jsonText = extractJson(generatePreview.rawResponse());
		log.info("Extracted JSON length={}chars", jsonText.length());
		JsonNode root = readRoot(jsonText);
		JsonNode schemesNode = requireArray(root, "schemes", "AI 输出顶层必须包含 schemes 数组");
		log.info("Parsing {} schemes from AI output...", schemesNode.size());
		List<String> validationMessages = new ArrayList<>();
		progressReporter.accept(new GenerationStatus("RUNNING", "parse", "校验方案结构和教学时长...", 65, null, 0, null));
		List<AllocationParsedScheme> schemes = parseSchemes(schemesNode, taskId, validationMessages);
		log.info("Parsed {} schemes, {} validation messages", schemes.size(), validationMessages.size());
		for (AllocationParsedScheme s : schemes) {
			log.info("  >> scheme=[{}], items={}",
				s.schemeName(), s.items() != null ? s.items().size() : 0);
		}
		if (!validationMessages.isEmpty()) {
			log.warn("Validation messages: {}", validationMessages);
		}
		log.info("=== ParseService generateParsePreview() end ===");
		return new AllocationParsePreview(
			generatePreview.taskId(),
			generatePreview.taskName(),
			generatePreview.rawResponse(),
			schemes,
			validationMessages
		);
	}

	private String extractJson(String rawResponse) {
		if (!StringUtils.hasText(rawResponse)) {
			throw new ValidationException("AI 原始响应为空，无法解析 JSON");
		}
		String content = rawResponse.trim();
		Matcher matcher = CODE_FENCE_PATTERN.matcher(content);
		if (matcher.find()) {
			return matcher.group(1).trim();
		}
		int start = content.indexOf('{');
		int end = content.lastIndexOf('}');
		if (start >= 0 && end > start) {
			return content.substring(start, end + 1).trim();
		}
		throw new ValidationException("AI 原始响应中未找到 JSON 对象");
	}

	private JsonNode readRoot(String jsonText) {
		try {
			// AI 可能在 JSON 中添加 // 注释，启用 ALLOW_COMMENTS 以兼容
			JsonNode root = objectMapper.reader()
				.with(tools.jackson.core.json.JsonReadFeature.ALLOW_JAVA_COMMENTS)
				.readTree(jsonText);
			if (root == null || !root.isObject()) {
				throw new ValidationException("AI 输出 JSON 顶层必须是对象");
			}
			return root;
		} catch (JacksonException exception) {
			throw new ValidationException("AI 输出 JSON 解析失败：" + exception.getOriginalMessage());
		}
	}

	private List<AllocationParsedScheme> parseSchemes(JsonNode schemesNode, Long taskId, List<String> validationMessages) {
		// 预加载该任务包含的所有教学任务
		AllocationTask task = allocationTaskMapper.findById(taskId);
		if (task == null) {
			throw new ResourceNotFoundException("排课任务不存在");
		}
		var taskResults = allocationTaskMapper.findTeachingTasks(taskId);
		Map<Long, TeachingTask> taskMap = taskResults.stream()
			.collect(Collectors.toMap(
				AllocationTaskTeachingTaskResult::getId,
				r -> {
					var tt = new TeachingTask();
					tt.setId(r.getId());
					tt.setTotalHours(r.getTotalHours());
					tt.setPrimaryTeacherId(r.getPrimaryTeacherId());
					tt.setClassroomId(r.getClassroomId());
					return tt;
				}
			));

		List<AllocationParsedScheme> schemes = new ArrayList<>();
		for (int i = 0; i < schemesNode.size(); i++) {
			JsonNode schemeNode = schemesNode.get(i);
			int schemeNumber = i + 1;
			if (schemeNode == null || !schemeNode.isObject()) {
				throw new ValidationException("第 " + schemeNumber + " 个方案必须是对象");
			}
			String schemeName = requireText(schemeNode, "schemeName", "第 " + schemeNumber + " 个方案 schemeName 不能为空");
			JsonNode itemsNode = requireArray(schemeNode, "items", "第 " + schemeNumber + " 个方案 items 必须是数组");
			schemes.add(new AllocationParsedScheme(
				schemeName,
				optionalText(schemeNode.get("summary")),
				optionalText(schemeNode.get("satisfiedSummary")),
				parseItems(itemsNode, schemeNumber, taskMap, task)
			));
		}
		return schemes;
	}

	private List<AllocationParsedItem> parseItems(JsonNode itemsNode, int schemeNumber,
		Map<Long, TeachingTask> taskMap, AllocationTask task) {
		List<AllocationParsedItem> items = new ArrayList<>();
		Map<Long, Integer> itemCountByTaskId = new java.util.HashMap<>();
		for (int i = 0; i < itemsNode.size(); i++) {
			JsonNode itemNode = itemsNode.get(i);
			int itemNumber = i + 1;
			if (itemNode == null || !itemNode.isArray() || itemNode.size() < 2) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细必须是 [teachingTaskId, timeSlotId] 数组");
			}
			Long teachingTaskId = itemNode.get(0).longValue();
			Long timeSlotId = itemNode.get(1).longValue();
			if (teachingTaskId == null || teachingTaskId <= 0) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 teachingTaskId 必须大于0");
			}
			if (timeSlotId == null || timeSlotId <= 0) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 timeSlotId 必须大于0");
			}

			// 校验教学任务属于当前排课任务
			TeachingTask teachingTask = taskMap.get(teachingTaskId);
			if (teachingTask == null) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 teachingTaskId="
					+ teachingTaskId + " 不属于当前排课任务");
			}

			// classroomId 已从 LLM 输出中移除，由后端自动从教学任务固定教室填充
			validateExists("timeSlotId", timeSlotId, schemeNumber, itemNumber, () -> timeSlotService.findById(timeSlotId));


			// 校验 timeSlot 在 startWeek-endWeek 范围内
			var timeSlot = timeSlotService.findById(timeSlotId);
			if (task.getStartWeek() != null && timeSlot.getWeekNumber() < task.getStartWeek()) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 timeSlotId="
					+ timeSlotId + " 所在周次 " + timeSlot.getWeekNumber() + " 小于任务起始周次 " + task.getStartWeek());
			}
			if (task.getEndWeek() != null && timeSlot.getWeekNumber() > task.getEndWeek()) {
				throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 timeSlotId="
					+ timeSlotId + " 所在周次 " + timeSlot.getWeekNumber() + " 大于任务结束周次 " + task.getEndWeek());
			}

			items.add(new AllocationParsedItem(teachingTaskId, timeSlotId));
			itemCountByTaskId.merge(teachingTaskId, 1, Integer::sum);
		}

		// 校验每个教学任务的片段数量 = totalHours / 2
		for (Map.Entry<Long, TeachingTask> entry : taskMap.entrySet()) {
			Long taskId = entry.getKey();
			TeachingTask tt = entry.getValue();
			int expectedCount = tt.getTotalHours() / 2;
			int actualCount = itemCountByTaskId.getOrDefault(taskId, 0);
			if (actualCount != expectedCount) {
				throw new ValidationException("教学任务ID " + taskId + " 需要 " + expectedCount
					+ " 个排课片段，实际只有 " + actualCount + " 个");
			}
		}

		return items;
	}

	private JsonNode requireArray(JsonNode parent, String fieldName, String message) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull() || !node.isArray()) {
			throw new ValidationException(message);
		}
		return node;
	}

	private String requireText(JsonNode parent, String fieldName, String message) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull()) {
			throw new ValidationException(message);
		}
		if (!node.isTextual()) {
			throw new ValidationException(message.replace("不能为空", "必须是字符串"));
		}
		String value = node.asText().trim();
		if (!StringUtils.hasText(value)) {
			throw new ValidationException(message);
		}
		return value;
	}

	private String optionalText(JsonNode node) {
		if (node == null || node.isNull()) {
			return null;
		}
		return node.isTextual() ? node.asText().trim() : node.asText();
	}

	private Long requireId(JsonNode parent, String fieldName, int schemeNumber, int itemNumber) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull()) {
			throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 不能为空");
		}
		Long value = parseLong(node);
		if (value == null) {
			throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 必须是整数");
		}
		if (value <= 0) {
			throw new ValidationException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 必须大于0");
		}
		return value;
	}

	private Long parseLong(JsonNode node) {
		if (node.isIntegralNumber() && node.canConvertToLong()) {
			return node.longValue();
		}
		if (node.isTextual()) {
			try {
				return Long.parseLong(node.asText().trim());
			} catch (NumberFormatException exception) {
				return null;
			}
		}
		return null;
	}

	private void validateExists(
		String fieldName,
		Long id,
		int schemeNumber,
		int itemNumber,
		Supplier<Object> lookup
	) {
		try {
			lookup.get();
		} catch (BusinessException exception) {
			throw new ValidationException(
				"第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 不存在：" + id
			);
		}
	}
}
