package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.OpenAiChatClient;
import com.yuy.eduflow.rag.OpenAiEmbeddingClient;
import com.yuy.eduflow.rag.QdrantVectorStoreClient;
import com.yuy.eduflow.rag.VectorSearchResult;
import com.yuy.eduflow.teacher.TeacherProfile;
import com.yuy.eduflow.teacher.TeacherProfileMapper;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Service
public class TeacherPenaltyResolver {
	private final TeacherProfileMapper teacherProfileMapper;
	private final OpenAiEmbeddingClient embeddingClient;
	private final QdrantVectorStoreClient vectorStoreClient;
	private final OpenAiChatClient chatClient;
	private final ObjectMapper objectMapper;

	public TeacherPenaltyResolver(
		TeacherProfileMapper teacherProfileMapper,
		OpenAiEmbeddingClient embeddingClient,
		QdrantVectorStoreClient vectorStoreClient,
		OpenAiChatClient chatClient,
		ObjectMapper objectMapper
	) {
		this.teacherProfileMapper = teacherProfileMapper;
		this.embeddingClient = embeddingClient;
		this.vectorStoreClient = vectorStoreClient;
		this.chatClient = chatClient;
		this.objectMapper = objectMapper;
	}

	public Map<String, Object> resolve(List<AllocationTaskTeachingTaskResult> teachingTasks) {
		Map<String, Object> fallback = fallbackPayload(teachingTasks);
		try {
			List<Long> teacherIds = uniqueTeacherIds(teachingTasks);
			String query = buildQuery(teachingTasks);
			log.info("Teacher profile RAG resolve start: taskCount={}, teacherIds={}, query={}", teachingTasks.size(), teacherIds, query);
			List<Double> vector = embeddingClient.embed(query);
			int topK = Math.min(Math.max(teacherIds.size(), 5), 50);
			List<VectorSearchResult> results = vectorStoreClient.search(vector, topK, "ACTIVE", teacherIds);
			List<Map<String, Object>> profiles = results.stream()
				.map(VectorSearchResult::payload)
				.toList();
			log.info("Teacher profile RAG retrieved: profileCount={}, topK={}, requestedTeacherIds={}, returnedTeacherIds={}",
				profiles.size(), topK, teacherIds, results.stream().map(VectorSearchResult::teacherId).toList());
			if (profiles.isEmpty()) {
				return fallback;
			}
			Map<String, Object> llmInput = new LinkedHashMap<>();
			llmInput.put("teaching_tasks", teachingTasks.stream().map(this::taskPayload).toList());
			llmInput.put("teacher_profiles", profiles);
			String userPrompt = readResource("prompts/teacher-penalty-user-template.md")
				.replace("{payload_json}", objectMapper.writeValueAsString(llmInput));
			String content = chatClient.generate(readResource("prompts/teacher-penalty-system.md"), userPrompt);
			@SuppressWarnings("unchecked")
			Map<String, Object> parsed = objectMapper.readValue(content, Map.class);
			Map<String, Object> normalized = normalizePayload(parsed);
			if (isEmptyPenaltyPayload(normalized)) {
				log.warn("Teacher profile RAG returned empty penalties, fallback to MySQL profiles");
				return fallback;
			}
			log.info("Teacher profile RAG resolved: {}", summarize(normalized));
			return normalized;
		} catch (Exception ex) {
			log.warn("Teacher profile RAG failed, fallback to MySQL profiles: {}", ex.getMessage());
			return fallback;
		}
	}

	private Map<String, Object> fallbackPayload(List<AllocationTaskTeachingTaskResult> teachingTasks) {
		Map<String, Object> penalties = new LinkedHashMap<>();
		for (Long teacherId : uniqueTeacherIds(teachingTasks)) {
			TeacherProfile profile = teacherProfileMapper.findByTeacherId(teacherId);
			if (profile == null) {
				continue;
			}
			Map<String, Object> item = new LinkedHashMap<>();
			item.put("teacher_id", teacherId);
			item.put("unavailable_slots", parseUnavailableTime(profile.getUnavailableTimeText()));
			item.put("max_weekly_hours", parseMaxWeeklyHours(profile.getWorkloadRequirement()));
			item.put("penalty_weight", 0.05);
			item.put("reason", "Java MySQL teacher_profile fallback");
			penalties.put(String.valueOf(teacherId), item);
		}
		Map<String, Object> payload = Map.of("teacher_penalties", penalties);
		log.info("Teacher profile fallback resolved: {}", summarize(payload));
		return payload;
	}

	private Map<String, Object> normalizePayload(Map<String, Object> raw) {
		Object value = raw.getOrDefault("teacher_penalties", raw);
		if (!(value instanceof Map<?, ?> rawPenalties)) {
			return Map.of("teacher_penalties", Map.of());
		}
		Map<String, Object> penalties = new LinkedHashMap<>();
		for (Map.Entry<?, ?> entry : rawPenalties.entrySet()) {
			if (!(entry.getValue() instanceof Map<?, ?> rawItem)) {
				continue;
			}
			Object teacherId = rawItem.containsKey("teacher_id") ? rawItem.get("teacher_id") : entry.getKey();
			if (teacherId == null) {
				continue;
			}
			Map<String, Object> item = new LinkedHashMap<>();
			item.put("teacher_id", longValue(teacherId));
			item.put("unavailable_slots", rawItem.containsKey("unavailable_slots") ? rawItem.get("unavailable_slots") : List.of());
			item.put("max_weekly_hours", rawItem.get("max_weekly_hours"));
			item.put("penalty_weight", rawItem.containsKey("penalty_weight") ? rawItem.get("penalty_weight") : 0.05);
			item.put("reason", rawItem.containsKey("reason") ? rawItem.get("reason") : "Java RAG teacher profile");
			penalties.put(String.valueOf(teacherId), item);
		}
		return Map.of("teacher_penalties", penalties);
	}

	private boolean isEmptyPenaltyPayload(Map<String, Object> payload) {
		Object penalties = payload.get("teacher_penalties");
		return !(penalties instanceof Map<?, ?> map) || map.isEmpty();
	}

	private List<Long> uniqueTeacherIds(List<AllocationTaskTeachingTaskResult> teachingTasks) {
		return teachingTasks.stream()
			.map(AllocationTaskTeachingTaskResult::getPrimaryTeacherId)
			.filter(id -> id != null && id > 0)
			.distinct()
			.toList();
	}

	private String buildQuery(List<AllocationTaskTeachingTaskResult> teachingTasks) {
		Map<Long, String> teacherNames = new LinkedHashMap<>();
		for (AllocationTaskTeachingTaskResult task : teachingTasks) {
			Long teacherId = task.getPrimaryTeacherId();
			if (teacherId != null && teacherId > 0) {
				teacherNames.putIfAbsent(teacherId, safe(task.getPrimaryTeacherName()));
			}
		}
		List<String> parts = new ArrayList<>();
		for (Map.Entry<Long, String> entry : teacherNames.entrySet()) {
			parts.add("教师" + entry.getKey() + " " + entry.getValue());
		}
		return "本次排课参与教师画像检索：" + String.join("；", parts)
			+ "。请检索这些教师的不可用时间、可用时间、工作量要求和特殊说明。";
	}

	private Map<String, Object> taskPayload(AllocationTaskTeachingTaskResult task) {
		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("teaching_task_id", task.getId());
		payload.put("teacher_id", task.getPrimaryTeacherId());
		payload.put("teacher_name", task.getPrimaryTeacherName());
		payload.put("course_name", task.getCourseName());
		payload.put("total_hours", task.getTotalHours());
		return payload;
	}

	private List<List<Integer>> parseUnavailableTime(String text) {
		List<List<Integer>> slots = new ArrayList<>();
		if (text == null || text.isBlank()) {
			return slots;
		}
		Map<String, Integer> dayMap = Map.of("周一", 1, "周二", 2, "周三", 3, "周四", 4, "周五", 5, "周六", 6, "周日", 7);
		Map<String, List<Integer>> timeMap = new LinkedHashMap<>();
		timeMap.put("全天", List.of(1, 2, 3, 4, 5));
		timeMap.put("上午", List.of(1, 2));
		timeMap.put("下午", List.of(3, 4, 5));
		timeMap.put("第一节", List.of(1));
		timeMap.put("第1节", List.of(1));
		timeMap.put("第二节", List.of(2));
		timeMap.put("第2节", List.of(2));
		timeMap.put("第三节", List.of(3));
		timeMap.put("第3节", List.of(3));
		timeMap.put("第四节", List.of(4));
		timeMap.put("第4节", List.of(4));
		timeMap.put("第五节", List.of(5));
		timeMap.put("第5节", List.of(5));
		for (Map.Entry<String, Integer> day : dayMap.entrySet()) {
			if (!text.contains(day.getKey())) {
				continue;
			}
			for (Map.Entry<String, List<Integer>> time : timeMap.entrySet()) {
				if (text.contains(time.getKey())) {
					for (Integer period : time.getValue()) {
						slots.add(List.of(day.getValue(), period));
					}
				}
			}
		}
		return slots.stream().distinct().toList();
	}

	private Integer parseMaxWeeklyHours(String text) {
		if (text == null || text.isBlank()) {
			return null;
		}
		java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("(\\d+)\\s*课时").matcher(text);
		return matcher.find() ? Integer.valueOf(matcher.group(1)) : null;
	}

	private Long longValue(Object value) {
		return value instanceof Number number ? number.longValue() : Long.valueOf(String.valueOf(value));
	}

	private String summarize(Map<String, Object> payload) {
		Object penalties = payload.get("teacher_penalties");
		return penalties instanceof Map<?, ?> map ? "teacherCount=" + map.size() : "teacherCount=0";
	}

	private String readResource(String path) throws IOException {
		try (InputStream inputStream = new ClassPathResource(path).getInputStream()) {
			return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8).trim();
		}
	}

	private String safe(String value) {
		return value == null ? "未知" : value;
	}
}
