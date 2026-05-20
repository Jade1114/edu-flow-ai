package com.yuy.eduflow.rag;

import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherProfile;
import com.yuy.eduflow.teacher.TeacherProfileMapper;
import com.yuy.eduflow.teacher.TeacherService;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.util.StringUtils;

@Slf4j
@Service
public class TeacherProfileVectorService {
	private final TeacherService teacherService;
	private final TeacherProfileMapper teacherProfileMapper;
	private final OpenAiEmbeddingClient embeddingClient;
	private final QdrantVectorStoreClient vectorStoreClient;

	public TeacherProfileVectorService(
		TeacherService teacherService,
		TeacherProfileMapper teacherProfileMapper,
		OpenAiEmbeddingClient embeddingClient,
		QdrantVectorStoreClient vectorStoreClient
	) {
		this.teacherService = teacherService;
		this.teacherProfileMapper = teacherProfileMapper;
		this.embeddingClient = embeddingClient;
		this.vectorStoreClient = vectorStoreClient;
	}

	public TeacherProfile indexTeacherProfile(Long teacherId) {
		log.info("=== indexTeacherProfile() start === teacherId={}", teacherId);
		Teacher teacher = teacherService.findById(teacherId);
		TeacherProfile profile = teacherProfileMapper.findByTeacherId(teacherId);
		log.info("re-fetched profile from DB: {}", profile);
		if (profile == null) {
			log.warn("teacher id={} has no teacher_profile, skipping vector index (probably ADMIN or no profile set)", teacherId);
			return null;
		}
        String vectorText = buildVectorText(teacher, profile);
		if (!StringUtils.hasText(vectorText)) {
			log.error("vectorText is empty for profile id={}", profile.getId());
			throw new ValidationException("教师画像文本不能为空");
		}
		log.debug("embedding vectorText=[{}]...", vectorText);
		List<Double> vector = embeddingClient.embed(vectorText);
		log.info("embedding done, vector size={}", vector.size());
		log.info("upserting to Qdrant... profileId={}", profile.getId());
		vectorStoreClient.upsert(profile.getId(), vector, buildPayload(teacher, profile, vectorText));
		log.info("Qdrant upsert done");
		TeacherProfile result = teacherProfileMapper.findByTeacherId(teacherId);
		log.info("=== indexTeacherProfile() end === teacherId={}", teacherId);
		return result;
	}

	public List<VectorSearchResult> search(String query, Integer topK, String status) {
		if (!StringUtils.hasText(query)) {
			throw new ValidationException("检索内容不能为空");
		}
		int limit = topK == null ? 5 : topK;
		if (limit <= 0 || limit > 20) {
			throw new ValidationException("topK 必须在 1 到 20 之间");
		}
		String filterStatus = StringUtils.hasText(status) ? status.trim() : ActiveStatus.ACTIVE.code();
		long t0 = System.currentTimeMillis();
		log.info("RAG search: calling embedding API... queryLength={}chars", query.length());
		List<Double> vector = embeddingClient.embed(query.trim());
		log.info("[{}ms] Embedding done, vectorSize={}", System.currentTimeMillis() - t0, vector.size());
		log.info("RAG search: calling Qdrant...");
		List<VectorSearchResult> results = vectorStoreClient.search(vector, limit, filterStatus);
		log.info("[{}ms] Qdrant search done, results={}", System.currentTimeMillis() - t0, results.size());
		return results;
	}

    private String buildVectorText(Teacher teacher, TeacherProfile profile) {
        StringBuilder builder = new StringBuilder();
        if (StringUtils.hasText(profile.getAvailabilityMatrixJson())) {
            builder.append(teacher.getName()).append("已维护固定周可用性矩阵，-1 表示明确不可用，0 表示随意分配，1 表示明确可用。\n");
        }
        if (StringUtils.hasText(profile.getProfileNote())) {
            builder.append(teacher.getName()).append("其他排课说明：").append(profile.getProfileNote()).append("。\n");
        }
        if (StringUtils.hasText(profile.getProfilePreferenceJson())) {
            builder.append(teacher.getName()).append("LLM 结构化软约束：").append(profile.getProfilePreferenceJson());
        }
        return builder.toString().trim();
    }

	private Map<String, Object> buildPayload(Teacher teacher, TeacherProfile profile, String vectorText) {
		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("teacherId", teacher.getId());
		payload.put("profileId", profile.getId());
		payload.put("teacherName", teacher.getName());
		payload.put("department", teacher.getDepartment());
		payload.put("title", teacher.getTitle());
		payload.put("status", teacher.getStatus().code());
        payload.put("availabilityMatrixJson", profile.getAvailabilityMatrixJson());
        payload.put("profileNote", profile.getProfileNote());
        payload.put("profilePreferenceJson", profile.getProfilePreferenceJson());
		payload.put("vectorText", vectorText);
		return payload;
	}
}
