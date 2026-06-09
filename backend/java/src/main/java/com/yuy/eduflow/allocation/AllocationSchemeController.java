package com.yuy.eduflow.allocation;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.conflict.ConflictDiagnosis;
import com.yuy.eduflow.ml.MlFeedbackEvent;
import com.yuy.eduflow.ml.MlFeedbackEventMarkRequest;
import com.yuy.eduflow.ml.MlFeedbackEventService;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/allocation-schemes")
public class AllocationSchemeController {
		private final AllocationSchemeService allocationSchemeService;
	private final AllocationItemService allocationItemService;
	private final AllocationSchemeConfirmService allocationSchemeConfirmService;
	private final AllocationItemAdjustmentLogMapper adjustmentLogMapper;
	private final MlFeedbackEventService feedbackEventService;
	private final AllocationTaskService allocationTaskService;
	private final AllocationTemplateMapper allocationTemplateMapper;
	private final ObjectMapper objectMapper = new ObjectMapper();

	public AllocationSchemeController(
		AllocationSchemeService allocationSchemeService,
		AllocationItemService allocationItemService,
		AllocationSchemeConfirmService allocationSchemeConfirmService,
		AllocationItemAdjustmentLogMapper adjustmentLogMapper,
		MlFeedbackEventService feedbackEventService,
		AllocationTaskService allocationTaskService,
		AllocationTemplateMapper allocationTemplateMapper
	) {
		this.allocationSchemeService = allocationSchemeService;
		this.allocationItemService = allocationItemService;
		this.allocationSchemeConfirmService = allocationSchemeConfirmService;
		this.adjustmentLogMapper = adjustmentLogMapper;
		this.feedbackEventService = feedbackEventService;
		this.allocationTaskService = allocationTaskService;
		this.allocationTemplateMapper = allocationTemplateMapper;
	}

	@GetMapping
	public ApiResponse<List<AllocationScheme>> findAll(
		@RequestParam(required = false) Long taskId,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(allocationSchemeService.findAll(taskId, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<AllocationScheme> findById(@PathVariable Long id) {
		return ApiResponse.success(allocationSchemeService.findById(id));
	}

	@GetMapping("/{id}/items")
	public ApiResponse<List<AllocationItemView>> findItems(@PathVariable Long id) {
		AllocationScheme scheme = allocationSchemeService.findById(id);
		String modelVersion = scheme.getModelVersion();
		if (modelVersion != null && modelVersion.startsWith("v3.5")) {
			return ApiResponse.success(findV35Items(scheme));
		}
		return ApiResponse.success(allocationItemService.findViewsBySchemeId(id));
	}

	@GetMapping("/{id}/conflicts")
	public ApiResponse<ConflictDiagnosis> findConflicts(@PathVariable Long id) {
		allocationSchemeService.findById(id);
		return ApiResponse.success(allocationSchemeService.findConflictDiagnosis(id));
	}

	@PostMapping
	public ApiResponse<AllocationScheme> create(@RequestBody AllocationSchemeRequest request) {
		return ApiResponse.success(allocationSchemeService.create(request));
	}

	@PostMapping("/{id}/confirm")
	public ApiResponse<AllocationConfirmResult> confirm(@PathVariable Long id) {
		return ApiResponse.success(allocationSchemeConfirmService.confirm(id));
	}

	@PostMapping("/{id}/reevaluate")
	public ApiResponse<AllocationScheme> reevaluate(@PathVariable Long id) {
		return ApiResponse.success(allocationItemService.reevaluateScheme(id));
	}

	@PutMapping("/{id}")
	public ApiResponse<AllocationScheme> update(@PathVariable Long id, @RequestBody AllocationSchemeRequest request) {
		return ApiResponse.success(allocationSchemeService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		allocationSchemeService.delete(id);
		return ApiResponse.success();
	}

	@PostMapping("/{schemeId}/adjustment-log")
	public ApiResponse<Void> recordAdjustment(
		@PathVariable Long schemeId,
		@RequestBody AdjustmentLogRequest request
	) {
		AllocationItemAdjustmentLog log = new AllocationItemAdjustmentLog();
		log.setSchemeId(schemeId);
		log.setItemId(request.itemId());
		log.setTeachingTaskId(request.teachingTaskId());
		log.setFromTimeSlotId(request.fromTimeSlotId());
		log.setToTimeSlotId(request.toTimeSlotId());
		log.setFromClassroomId(request.fromClassroomId());
		log.setToClassroomId(request.toClassroomId());
		log.setReason(request.reason());
		adjustmentLogMapper.insert(log);
		return ApiResponse.success();
	}

	@PutMapping("/{schemeId}/items/{itemId}")
	public ApiResponse<List<AllocationItemView>> moveItem(
		@PathVariable Long schemeId,
		@PathVariable Long itemId,
		@RequestBody AllocationItemMoveRequest request
	) {
		return ApiResponse.success(allocationItemService.moveAndRecheck(schemeId, itemId, request));
	}

	@PostMapping("/{schemeId}/items/{itemId}/feedback")
	public ApiResponse<MlFeedbackEvent> markItem(
		@PathVariable Long schemeId,
		@PathVariable Long itemId,
		@RequestBody MlFeedbackEventMarkRequest request
	) {
		return ApiResponse.success(feedbackEventService.markItem(schemeId, itemId, request));
	}

	private List<AllocationItemView> findV35Items(AllocationScheme scheme) {
		Long taskId = scheme.getTaskId();
		String generationRunId = extractGenerationRunId(scheme);
		List<AllocationTemplateWeek> weeks = generationRunId != null && !generationRunId.isBlank()
			? allocationTemplateMapper.findTemplateWeeksByRun(taskId, generationRunId)
			: allocationTemplateMapper.findTemplateWeeks(taskId);
		if (weeks.isEmpty()) return Collections.emptyList();

		List<AllocationItemView> allItems = new ArrayList<>();
		long virtualItemId = 0;

		for (AllocationTemplateWeek week : weeks) {
			List<AllocationTemplateTimetableEntry> entries = generationRunId != null && !generationRunId.isBlank()
				? allocationTemplateMapper.findWeekTimetableByRun(taskId, generationRunId, week.getWeekNumber())
				: allocationTemplateMapper.findWeekTimetable(taskId, week.getWeekNumber());
			for (AllocationTemplateTimetableEntry e : entries) {
				virtualItemId--;
				AllocationItemView view = new AllocationItemView();
				view.setId(virtualItemId);
				view.setSchemeId(scheme.getId());
				view.setCourseName(e.getCourseName());
				view.setTeacherName(e.getTeacherName() != null && !e.getTeacherName().isBlank() ? e.getTeacherName() : null);
				view.setClassGroupName(e.getClassName());
				view.setClassroomName(e.getClassroomName());
				view.setWeekNumber(e.getWeekNumber());
				view.setDayOfWeek(e.getDayOfWeek());
				view.setPeriodIndex(e.getPeriodIndex());
				view.setValid(true);
				allItems.add(view);
			}
		}
		return allItems;
	}

	private String extractGenerationRunId(AllocationScheme scheme) {
		String summary = scheme.getSummary();
		if (summary == null || summary.isBlank()) return null;
		try {
			Map<String, Object> data = objectMapper.readValue(summary, new TypeReference<>() {});
			Object value = data.get("generation_run_id");
			return value == null ? null : String.valueOf(value);
		} catch (Exception ignored) {
			return null;
		}
	}
}
