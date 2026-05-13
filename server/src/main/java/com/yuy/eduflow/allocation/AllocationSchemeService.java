package com.yuy.eduflow.allocation;

import com.yuy.eduflow.enums.SchemeStatus;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationSchemeService {
	

	private final AllocationSchemeMapper allocationSchemeMapper;

	public AllocationSchemeService(AllocationSchemeMapper allocationSchemeMapper) {
		this.allocationSchemeMapper = allocationSchemeMapper;
	}

	public List<AllocationScheme> findAll(Long taskId, String status) {
		if (taskId != null && taskId <= 0) {
			throw new IllegalArgumentException("分课任务ID必须大于0");
		}
		return allocationSchemeMapper.findAll(taskId, status);
	}

	public AllocationScheme findById(Long id) {
		AllocationScheme scheme = allocationSchemeMapper.findById(id);
		if (scheme == null) {
			throw new IllegalArgumentException("分课方案不存在");
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

	private AllocationScheme toScheme(AllocationScheme scheme, AllocationSchemeRequest request) {
		requirePositiveId(request.taskId(), "分课任务ID不能为空");
		if (!StringUtils.hasText(request.schemeName())) {
			throw new IllegalArgumentException("分课方案名称不能为空");
		}
		if (request.score() != null && (request.score() < 0 || request.score() > 100)) {
			throw new IllegalArgumentException("分课方案评分必须在0到100之间");
		}
		scheme.setTaskId(request.taskId());
		scheme.setSchemeName(request.schemeName().trim());
		scheme.setSummary(clean(request.summary()));
		scheme.setScore(request.score());
		scheme.setSatisfiedSummary(clean(request.satisfiedSummary()));
		scheme.setConflictSummary(clean(request.conflictSummary()));
		scheme.setValid(request.valid() != null ? request.valid() : true);
		scheme.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : SchemeStatus.CANDIDATE.code());
		return scheme;
	}

	private void requirePositiveId(Long id, String emptyMessage) {
		if (id == null) {
			throw new IllegalArgumentException(emptyMessage);
		}
		if (id <= 0) {
			throw new IllegalArgumentException(emptyMessage.replace("不能为空", "必须大于0"));
		}
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
