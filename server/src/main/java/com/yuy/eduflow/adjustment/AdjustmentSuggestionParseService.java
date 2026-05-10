package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.classroom.ClassroomService;
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
public class AdjustmentSuggestionParseService {
	private static final Pattern CODE_FENCE_PATTERN = Pattern.compile(
		"```\\s*(?:json)?\\s*([\\s\\S]*?)```",
		Pattern.CASE_INSENSITIVE
	);

	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;
	private final ObjectMapper objectMapper;

	public AdjustmentSuggestionParseService(
		ClassroomService classroomService,
		TimeSlotService timeSlotService,
		ObjectMapper objectMapper
	) {
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
		this.objectMapper = objectMapper;
	}

	public AdjustmentSuggestionPreview parse(Long requestId, Long assignmentId, String rawResponse) {
		String jsonText = extractJson(rawResponse);
		JsonNode root = readRoot(jsonText);
		JsonNode candidatesNode = requireArray(root, "candidates", "AI 输出顶层必须包含 candidates 数组");
		List<String> validationMessages = new ArrayList<>();
		List<AdjustmentSuggestionCandidate> candidates = parseCandidates(candidatesNode, validationMessages);
		return new AdjustmentSuggestionPreview(
			requestId,
			assignmentId,
			rawResponse,
			candidates,
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

	private List<AdjustmentSuggestionCandidate> parseCandidates(JsonNode candidatesNode, List<String> validationMessages) {
		List<AdjustmentSuggestionCandidate> candidates = new ArrayList<>();
		for (int i = 0; i < candidatesNode.size(); i++) {
			JsonNode candidateNode = candidatesNode.get(i);
			int candidateNumber = i + 1;
			if (candidateNode == null || !candidateNode.isObject()) {
				throw new IllegalArgumentException("第 " + candidateNumber + " 个调课候选必须是对象");
			}
			Long newTimeSlotId = requireId(candidateNode, "newTimeSlotId", candidateNumber);
			Long newClassroomId = requireId(candidateNode, "newClassroomId", candidateNumber);
			validateExists("newTimeSlotId", newTimeSlotId, candidateNumber, () -> timeSlotService.findById(newTimeSlotId));
			validateExists("newClassroomId", newClassroomId, candidateNumber, () -> classroomService.findById(newClassroomId));
			candidates.add(new AdjustmentSuggestionCandidate(
				i,
				parseSummary(candidateNode, candidateNumber, validationMessages),
				newTimeSlotId,
				newClassroomId,
				true,
				null
			));
		}
		return candidates;
	}

	private String parseSummary(JsonNode candidateNode, int candidateNumber, List<String> validationMessages) {
		JsonNode summaryNode = candidateNode.get("summary");
		if (summaryNode == null || summaryNode.isNull()) {
			validationMessages.add("第 " + candidateNumber + " 个调课候选 summary 为空，已使用默认摘要");
			return "候选方案 " + candidateNumber;
		}
		String summary = summaryNode.isTextual() ? summaryNode.asText().trim() : summaryNode.asText();
		if (!StringUtils.hasText(summary)) {
			validationMessages.add("第 " + candidateNumber + " 个调课候选 summary 为空，已使用默认摘要");
			return "候选方案 " + candidateNumber;
		}
		return summary;
	}

	private JsonNode requireArray(JsonNode parent, String fieldName, String message) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull() || !node.isArray()) {
			throw new IllegalArgumentException(message);
		}
		return node;
	}

	private Long requireId(JsonNode parent, String fieldName, int candidateNumber) {
		JsonNode node = parent.get(fieldName);
		if (node == null || node.isNull()) {
			throw new IllegalArgumentException("第 " + candidateNumber + " 个调课候选 " + fieldName + " 不能为空");
		}
		Long value = parseLong(node);
		if (value == null) {
			throw new IllegalArgumentException("第 " + candidateNumber + " 个调课候选 " + fieldName + " 必须是整数");
		}
		if (value <= 0) {
			throw new IllegalArgumentException("第 " + candidateNumber + " 个调课候选 " + fieldName + " 必须大于0");
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

	private void validateExists(String fieldName, Long id, int candidateNumber, Supplier<Object> lookup) {
		try {
			lookup.get();
		} catch (IllegalArgumentException exception) {
			throw new IllegalArgumentException(
				"第 " + candidateNumber + " 个调课候选 " + fieldName + " 不存在：" + id
			);
		}
	}
}
