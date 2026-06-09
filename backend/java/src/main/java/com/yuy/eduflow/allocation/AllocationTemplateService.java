package com.yuy.eduflow.allocation;

import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class AllocationTemplateService {
	private final AllocationTaskService allocationTaskService;
	private final AllocationTemplateMapper allocationTemplateMapper;

	public AllocationTemplateService(
		AllocationTaskService allocationTaskService,
		AllocationTemplateMapper allocationTemplateMapper
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationTemplateMapper = allocationTemplateMapper;
	}

	public List<AllocationTemplate> findTemplates(Long allocationTaskId) {
		allocationTaskService.findById(allocationTaskId);
		String generationRunId = allocationTemplateMapper.findLatestGenerationRunId(allocationTaskId);
		return generationRunId == null
			? allocationTemplateMapper.findTemplates(allocationTaskId)
			: allocationTemplateMapper.findTemplatesByRun(allocationTaskId, generationRunId);
	}

	public List<AllocationTemplateWeek> findTemplateWeeks(Long allocationTaskId) {
		allocationTaskService.findById(allocationTaskId);
		String generationRunId = allocationTemplateMapper.findLatestGenerationRunId(allocationTaskId);
		return generationRunId == null
			? allocationTemplateMapper.findTemplateWeeks(allocationTaskId)
			: allocationTemplateMapper.findTemplateWeeksByRun(allocationTaskId, generationRunId);
	}

	public AllocationTemplateWeek findTemplateWeek(Long allocationTaskId, Integer weekNumber) {
		allocationTaskService.findById(allocationTaskId);
		return allocationTemplateMapper.findTemplateWeek(allocationTaskId, weekNumber);
	}

	public List<AllocationTemplateTimetableEntry> findWeekTimetable(Long allocationTaskId, Integer weekNumber) {
		allocationTaskService.findById(allocationTaskId);
		String generationRunId = allocationTemplateMapper.findLatestGenerationRunId(allocationTaskId);
		return generationRunId == null
			? allocationTemplateMapper.findWeekTimetable(allocationTaskId, weekNumber)
			: allocationTemplateMapper.findWeekTimetableByRun(allocationTaskId, generationRunId, weekNumber);
	}
}
