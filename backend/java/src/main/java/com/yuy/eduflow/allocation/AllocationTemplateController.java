package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/allocation-tasks/{allocationTaskId}/templates")
public class AllocationTemplateController {
	private final AllocationTemplateService allocationTemplateService;
	private final AllocationTaskService allocationTaskService;
	private final V35TemplateGenerationService v35TemplateGenerationService;

	public AllocationTemplateController(
		AllocationTemplateService allocationTemplateService,
		AllocationTaskService allocationTaskService,
		V35TemplateGenerationService v35TemplateGenerationService
	) {
		this.allocationTemplateService = allocationTemplateService;
		this.allocationTaskService = allocationTaskService;
		this.v35TemplateGenerationService = v35TemplateGenerationService;
	}

	@GetMapping
	public ApiResponse<List<AllocationTemplate>> findTemplates(@PathVariable Long allocationTaskId) {
		return ApiResponse.success(allocationTemplateService.findTemplates(allocationTaskId));
	}

	@GetMapping("/weeks")
	public ApiResponse<List<AllocationTemplateWeek>> findTemplateWeeks(@PathVariable Long allocationTaskId) {
		return ApiResponse.success(allocationTemplateService.findTemplateWeeks(allocationTaskId));
	}

	@GetMapping("/weeks/{weekNumber}")
	public ApiResponse<AllocationTemplateWeek> findTemplateWeek(
		@PathVariable Long allocationTaskId,
		@PathVariable Integer weekNumber
	) {
		return ApiResponse.success(allocationTemplateService.findTemplateWeek(allocationTaskId, weekNumber));
	}

	@GetMapping("/weeks/{weekNumber}/timetable")
	public ApiResponse<List<AllocationTemplateTimetableEntry>> findWeekTimetable(
		@PathVariable Long allocationTaskId,
		@PathVariable Integer weekNumber
	) {
		return ApiResponse.success(allocationTemplateService.findWeekTimetable(allocationTaskId, weekNumber));
	}

	@PostMapping("/generate")
	public ApiResponse<V35TemplateGenerationStatus> generateTemplates(
		@PathVariable Long allocationTaskId,
		@RequestBody(required = false) Map<String, Object> params
	) {
		allocationTaskService.findById(allocationTaskId);
		Integer totalWeeks = params != null && params.get("totalWeeks") != null
			? Integer.valueOf(params.get("totalWeeks").toString()) : 18;
		Integer topK = params != null && params.get("topK") != null
			? Integer.valueOf(params.get("topK").toString()) : 300;
		Integer maxTemplates = params != null && params.get("maxTemplates") != null
			? Integer.valueOf(params.get("maxTemplates").toString()) : 8;
		Boolean trainModel = params != null && Boolean.TRUE.equals(params.get("trainModel"));
		Boolean importDb = params != null && Boolean.TRUE.equals(params.get("importDb"));
		Boolean truncateDb = params != null && Boolean.TRUE.equals(params.get("truncateDb"));

		V35TemplateGenerationStatus status = v35TemplateGenerationService.startGeneration(
			allocationTaskId, totalWeeks, topK, maxTemplates, trainModel, importDb, truncateDb
		);
		return ApiResponse.success(status);
	}

	@GetMapping("/generation-status")
	public ApiResponse<V35TemplateGenerationStatus> generationStatus(@PathVariable Long allocationTaskId) {
		return ApiResponse.success(v35TemplateGenerationService.getStatus(allocationTaskId));
	}
}
