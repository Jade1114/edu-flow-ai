package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classgroup.ClassGroupService;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.course.CourseService;
import com.yuy.eduflow.teacher.TeacherService;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class AllocationGenerateParseService {
	private static final Pattern CODE_FENCE_PATTERN = Pattern.compile(
		"```\\s*(?:json)?\\s*([\\s\\S]*?)```",
		Pattern.CASE_INSENSITIVE
	);

	private final AllocationGeneratePreviewService allocationGeneratePreviewService;
	private final CourseService courseService;
	private final ClassGroupService classGroupService;
	private final TeacherService teacherService;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;
	private final ObjectMapper objectMapper;

	public AllocationGenerateParseService(
		AllocationGeneratePreviewService allocationGeneratePreviewService,
		CourseService courseService,
		ClassGroupService classGroupService,
		TeacherService teacherService,
		ClassroomService classroomService,
		TimeSlotService timeSlotService,
		ObjectMapper objectMapper
	) {
		this.allocationGeneratePreviewService = allocationGeneratePreviewService;
		this.courseService = courseService;
		this.classGroupService = classGroupService;
		this.teacherService = teacherService;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
		this.objectMapper = objectMapper;
	}

	public AllocationParsePreview generateParsePreview(Long taskId, Integer topK) {
		AllocationGeneratePreview generatePreview = allocationGeneratePreviewService.generate(taskId, topK);
		String jsonText = extractJson(generatePreview.rawResponse());
		JsonNode root = readRoot(jsonText);
		JsonNode schemesNode = requireArray(root, "schemes", "AI 输出顶层必须包含 schemes 数组");
		List<String> validationMessages = new ArrayList<>();
		List<AllocationParsedScheme> schemes = parseSchemes(schemesNode, validationMessages);
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
			throw new IllegalArgumentException("AI 原始响应为空，无法解析 JSON");
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
		throw new IllegalArgumentException("AI 原始响应中未找到 JSON 对象");
	}

	private JsonNode readRoot(String jsonText) {
		try {
			JsonNode root = objectMapper.readTree(jsonText);
			if (root == null || !root.isObject()) {
				throw new IllegalArgumentException("AI 输出 JSON 顶层必须是对象");
			}
			return root;
		} catch (JacksonException exception) {
			throw new IllegalArgumentException("AI 输出 JSON 解析失败：" + exception.getOriginalMessage());
		}
	}

	private List<AllocationParsedScheme> parseSchemes(JsonNode schemesNode, List<String> validationMessages) {
		List<AllocationParsedScheme> schemes = new ArrayList<>();
		for (int i = 0; i < schemesNode.size(); i++) {
			JsonNode schemeNode = schemesNode.get(i);
			int schemeNumber = i + 1;
			if (schemeNode == null || !schemeNode.isObject()) {
				throw new IllegalArgumentException("第 " + schemeNumber + " 个方案必须是对象");
			}
			String schemeName = requireText(schemeNode, "schemeName", "第 " + schemeNumber + " 个方案 schemeName 不能为空");
			JsonNode itemsNode = requireArray(schemeNode, "items", "第 " + schemeNumber + " 个方案 items 必须是数组");
			Integer score = parseScore(schemeNode.get("score"), schemeNumber, validationMessages);
			schemes.add(new AllocationParsedScheme(
				schemeName,
				optionalText(schemeNode.get("summary")),
				score,
				optionalText(schemeNode.get("satisfiedSummary")),
				parseItems(itemsNode, schemeNumber)
			));
		}
		return schemes;
	}

	private List<AllocationParsedItem> parseItems(JsonNode itemsNode, int schemeNumber) {
		List<AllocationParsedItem> items = new ArrayList<>();
		for (int i = 0; i < itemsNode.size(); i++) {
			JsonNode itemNode = itemsNode.get(i);
			int itemNumber = i + 1;
			if (itemNode == null || !itemNode.isObject()) {
				throw new IllegalArgumentException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细必须是对象");
			}
			Long courseId = requireId(itemNode, "courseId", schemeNumber, itemNumber);
			Long classGroupId = requireId(itemNode, "classGroupId", schemeNumber, itemNumber);
			Long teacherId = requireId(itemNode, "teacherId", schemeNumber, itemNumber);
			Long classroomId = requireId(itemNode, "classroomId", schemeNumber, itemNumber);
			Long timeSlotId = requireId(itemNode, "timeSlotId", schemeNumber, itemNumber);
			validateExists("courseId", courseId, schemeNumber, itemNumber, () -> courseService.findById(courseId));
			validateExists("classGroupId", classGroupId, schemeNumber, itemNumber, () -> classGroupService.findById(classGroupId));
			validateExists("teacherId", teacherId, schemeNumber, itemNumber, () -> teacherService.findById(teacherId));
			validateExists("classroomId", classroomId, schemeNumber, itemNumber, () -> classroomService.findById(classroomId));
			validateExists("timeSlotId", timeSlotId, schemeNumber, itemNumber, () -> timeSlotService.findById(timeSlotId));
			items.add(new AllocationParsedItem(courseId, classGroupId, teacherId, classroomId, timeSlotId));
		}
		return items;
	}

	private JsonNode requireArray(JsonNode parent, String fieldName, String message) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull() || !node.isArray()) {
			throw new IllegalArgumentException(message);
		}
		return node;
	}

	private String requireText(JsonNode parent, String fieldName, String message) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull()) {
			throw new IllegalArgumentException(message);
		}
		if (!node.isTextual()) {
			throw new IllegalArgumentException(message.replace("不能为空", "必须是字符串"));
		}
		String value = node.asText().trim();
		if (!StringUtils.hasText(value)) {
			throw new IllegalArgumentException(message);
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
			throw new IllegalArgumentException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 不能为空");
		}
		Long value = parseLong(node);
		if (value == null) {
			throw new IllegalArgumentException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 必须是整数");
		}
		if (value <= 0) {
			throw new IllegalArgumentException("第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 必须大于0");
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

	private Integer parseScore(JsonNode node, int schemeNumber, List<String> validationMessages) {
		if (node == null || node.isNull()) {
			return null;
		}
		Integer score = null;
		if (node.isIntegralNumber() && node.canConvertToInt()) {
			score = node.intValue();
		} else if (node.isNumber()) {
			double rawScore = node.doubleValue();
			if (Double.isFinite(rawScore) && rawScore <= Integer.MAX_VALUE && rawScore >= Integer.MIN_VALUE) {
				score = (int) Math.round(rawScore);
				validationMessages.add("第 " + schemeNumber + " 个方案 score 不是整数，已四舍五入为 " + score);
			} else {
				validationMessages.add("第 " + schemeNumber + " 个方案 score 超出整数范围，已置为空");
			}
		} else if (node.isTextual()) {
			String text = node.asText().trim();
			if (StringUtils.hasText(text)) {
				try {
					score = Integer.parseInt(text);
					validationMessages.add("第 " + schemeNumber + " 个方案 score 是字符串，已按整数解析");
				} catch (NumberFormatException exception) {
					validationMessages.add("第 " + schemeNumber + " 个方案 score 不是数字，已置为空");
				}
			}
		} else {
			validationMessages.add("第 " + schemeNumber + " 个方案 score 不是数字，已置为空");
		}
		if (score != null && (score < 0 || score > 100)) {
			validationMessages.add("第 " + schemeNumber + " 个方案 score=" + score + " 超出建议范围 0-100");
		}
		return score;
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
		} catch (IllegalArgumentException exception) {
			throw new IllegalArgumentException(
				"第 " + schemeNumber + " 个方案第 " + itemNumber + " 个明细 " + fieldName + " 不存在：" + id
			);
		}
	}
}
