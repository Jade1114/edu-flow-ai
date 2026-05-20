package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.Assert;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.conflict.ConflictCheckResult;
import com.yuy.eduflow.conflict.ConflictCheckResultMapper;
import com.yuy.eduflow.conflict.ConflictDiagnosis;
import com.yuy.eduflow.enums.SchemeStatus;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationSchemeService {

	private final AllocationSchemeMapper allocationSchemeMapper;
	private final ConflictCheckResultMapper conflictCheckResultMapper;

	public AllocationSchemeService(
		AllocationSchemeMapper allocationSchemeMapper,
		ConflictCheckResultMapper conflictCheckResultMapper
	) {
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.conflictCheckResultMapper = conflictCheckResultMapper;
	}

	public List<AllocationScheme> findAll(Long taskId, String status) {
		if (taskId != null && taskId <= 0) {
			throw new ValidationException("分课任务ID必须大于0");
		}
		return allocationSchemeMapper.findAll(taskId, status);
	}

	public AllocationScheme findById(Long id) {
		AllocationScheme scheme = allocationSchemeMapper.findById(id);
		if (scheme == null) {
			throw new ResourceNotFoundException("分课方案不存在");
		}
		return scheme;
	}

	public AllocationScheme create(AllocationSchemeRequest request) {
		AllocationScheme scheme = toScheme(new AllocationScheme(), request);
		allocationSchemeMapper.insert(scheme);
		return findById(scheme.getId());
	}

	public AllocationScheme update(Long id, AllocationSchemeRequest request) {
		AllocationScheme existing = findById(id);
		AllocationScheme scheme = toScheme(existing, request);
		allocationSchemeMapper.update(scheme);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		allocationSchemeMapper.updateStatus(id, SchemeStatus.REJECTED.code());
	}

	public ConflictDiagnosis findConflictDiagnosis(Long schemeId) {
		findById(schemeId);
		List<ConflictCheckResult> raw = conflictCheckResultMapper.findBySchemeId(schemeId);
		if (raw == null || raw.isEmpty()) {
			return new ConflictDiagnosis("该方案无明显冲突", 0, true, Map.of(), List.of());
		}

		Map<String, List<ConflictDiagnosis.ConflictDiagnosisItem>> groups = new LinkedHashMap<>();
		List<ConflictDiagnosis.ConflictDiagnosisItem> hoursMismatch = new ArrayList<>();

		String[] order = {"TEACHER_TIME", "CLASS_GROUP_TIME", "CLASSROOM_TIME", "TEACHER_WORKLOAD"};
		for (String type : order) {
			groups.put(type, new ArrayList<>());
		}

		for (ConflictCheckResult r : raw) {
			ConflictDiagnosis.ConflictDiagnosisItem item = new ConflictDiagnosis.ConflictDiagnosisItem(
				r.getId(),
				r.getConflictType(),
				typeLabel(r.getConflictType()),
				r.getMessage(),
				r.getRelatedTeacherId(),
				r.getRelatedTeacherName(),
				r.getRelatedClassGroupId(),
				r.getRelatedClassGroupName(),
				r.getRelatedClassroomId(),
				r.getRelatedClassroomName(),
				r.getRelatedTimeSlotId(),
				r.getRelatedTimeSlotLabel(),
				r.getTeachingTaskId(),
				r.getCourseName(),
				r.getExpectedHours(),
				r.getActualHours()
			);
			if ("TEACHING_TASK_HOURS".equals(r.getConflictType())) {
				hoursMismatch.add(item);
			} else {
				groups.computeIfAbsent(r.getConflictType(), k -> new ArrayList<>()).add(item);
			}
		}

		// Remove empty groups
		groups.entrySet().removeIf(e -> e.getValue().isEmpty());

		int total = raw.size();
		boolean clean = total == 0;
		String summary = buildSummary(total, groups, hoursMismatch);
		return new ConflictDiagnosis(summary, total, clean, groups, hoursMismatch);
	}

	private String typeLabel(String type) {
		return switch (type) {
			case "TEACHER_TIME" -> "教师时间冲突";
			case "CLASS_GROUP_TIME" -> "班级时间冲突";
			case "CLASSROOM_TIME" -> "教室时间冲突";
			case "TEACHER_WORKLOAD" -> "教师工作量冲突";
			case "TEACHING_TASK_HOURS" -> "教学任务课时不匹配";
			default -> "未知冲突";
		};
	}

	private String buildSummary(int total, Map<String, List<ConflictDiagnosis.ConflictDiagnosisItem>> groups, List<ConflictDiagnosis.ConflictDiagnosisItem> hoursMismatch) {
		if (total == 0) return "该方案无明显冲突";
		List<String> parts = new ArrayList<>();
		for (Map.Entry<String, List<ConflictDiagnosis.ConflictDiagnosisItem>> e : groups.entrySet()) {
			parts.add(typeLabel(e.getKey()) + " " + e.getValue().size() + " 条");
		}
		if (!hoursMismatch.isEmpty()) {
			parts.add("教学任务课时不匹配 " + hoursMismatch.size() + " 条");
		}
		return "共发现 " + total + " 条问题：" + String.join("，", parts);
	}

	private AllocationScheme toScheme(AllocationScheme scheme, AllocationSchemeRequest request) {
		Assert.positiveId(request.taskId(), "分课任务ID");
		if (!StringUtils.hasText(request.schemeName())) {
			throw new ValidationException("分课方案名称不能为空");
		}
		scheme.setTaskId(request.taskId());
		scheme.setSchemeName(request.schemeName().trim());
		scheme.setSummary(clean(request.summary()));
		scheme.setConflictSummary(clean(request.conflictSummary()));
		scheme.setValid(request.valid() != null ? request.valid() : true);
		scheme.setStatus(StringUtils.hasText(request.status()) ? SchemeStatus.from(request.status().trim()) : SchemeStatus.CANDIDATE);
		return scheme;
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
