package com.yuy.eduflow.rag;

import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherProfile;
import com.yuy.eduflow.teacher.TeacherProfileMapper;
import com.yuy.eduflow.teacher.TeacherService;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

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
		Teacher teacher = teacherService.findById(teacherId);
		TeacherProfile profile = teacherProfileMapper.findByTeacherId(teacherId);
		if (profile == null) {
			throw new IllegalArgumentException("教师个人情况不存在");
		}
		if (!StringUtils.hasText(profile.getVectorText())) {
			throw new IllegalArgumentException("教师画像文本不能为空");
		}
		List<Double> vector = embeddingClient.embed(profile.getVectorText());
		vectorStoreClient.upsert(profile.getId(), vector, buildPayload(teacher, profile));
		teacherProfileMapper.updateVectorIndexedByTeacherId(teacherId, true);
		return teacherProfileMapper.findByTeacherId(teacherId);
	}

	public List<VectorSearchResult> search(String query, Integer topK, String status) {
		if (!StringUtils.hasText(query)) {
			throw new IllegalArgumentException("检索内容不能为空");
		}
		int limit = topK == null ? 5 : topK;
		if (limit <= 0 || limit > 20) {
			throw new IllegalArgumentException("topK 必须在 1 到 20 之间");
		}
		String filterStatus = StringUtils.hasText(status) ? status.trim() : "ACTIVE";
		List<Double> vector = embeddingClient.embed(query.trim());
		return vectorStoreClient.search(vector, limit, filterStatus);
	}

	private Map<String, Object> buildPayload(Teacher teacher, TeacherProfile profile) {
		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("teacherId", teacher.getId());
		payload.put("profileId", profile.getId());
		payload.put("teacherName", teacher.getName());
		payload.put("department", teacher.getDepartment());
		payload.put("title", teacher.getTitle());
		payload.put("status", teacher.getStatus());
		payload.put("skillText", profile.getSkillText());
		payload.put("availableTimeText", profile.getAvailableTimeText());
		payload.put("unavailableTimeText", profile.getUnavailableTimeText());
		payload.put("workloadRequirement", profile.getWorkloadRequirement());
		payload.put("specialNote", profile.getSpecialNote());
		payload.put("vectorText", profile.getVectorText());
		return payload;
	}
}
