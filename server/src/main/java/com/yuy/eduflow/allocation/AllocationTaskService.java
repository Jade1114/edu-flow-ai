package com.yuy.eduflow.allocation;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationTaskService {
	private static final String DEFAULT_STATUS = "DRAFT";

	private final AllocationTaskMapper allocationTaskMapper;

	public AllocationTaskService(AllocationTaskMapper allocationTaskMapper) {
		this.allocationTaskMapper = allocationTaskMapper;
	}

	public List<AllocationTask> findAll(String keyword, String status) {
		return allocationTaskMapper.findAll(keyword, status);
	}

	public AllocationTask findById(Long id) {
		AllocationTask task = allocationTaskMapper.findById(id);
		if (task == null) {
			throw new IllegalArgumentException("分课任务不存在");
		}
		return task;
	}

	public AllocationTask create(AllocationTaskRequest request) {
		AllocationTask task = toTask(new AllocationTask(), request);
		allocationTaskMapper.insert(task);
		return findById(task.getId());
	}

	public AllocationTask update(Long id, AllocationTaskRequest request) {
		findById(id);
		AllocationTask task = toTask(new AllocationTask(), request);
		task.setId(id);
		allocationTaskMapper.update(task);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		allocationTaskMapper.cancel(id);
	}

	private AllocationTask toTask(AllocationTask task, AllocationTaskRequest request) {
		if (!StringUtils.hasText(request.name())) {
			throw new IllegalArgumentException("分课任务名称不能为空");
		}
		task.setName(request.name().trim());
		task.setDescription(clean(request.description()));
		task.setPriorityRule(clean(request.priorityRule()));
		task.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : DEFAULT_STATUS);
		task.setCreatedBy(clean(request.createdBy()));
		return task;
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
