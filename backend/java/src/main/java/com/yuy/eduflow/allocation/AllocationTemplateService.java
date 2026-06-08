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
		return allocationTemplateMapper.findTemplates(allocationTaskId);
	}

	public List<AllocationTemplateWeek> findTemplateWeeks(Long allocationTaskId) {
		allocationTaskService.findById(allocationTaskId);
		return allocationTemplateMapper.findTemplateWeeks(allocationTaskId);
	}

	public AllocationTemplateWeek findTemplateWeek(Long allocationTaskId, Integer weekNumber) {
		allocationTaskService.findById(allocationTaskId);
		return allocationTemplateMapper.findTemplateWeek(allocationTaskId, weekNumber);
	}

	public List<AllocationTemplateTimetableEntry> findWeekTimetable(Long allocationTaskId, Integer weekNumber) {
		allocationTaskService.findById(allocationTaskId);
		return allocationTemplateMapper.findWeekTimetable(allocationTaskId, weekNumber);
	}
}
