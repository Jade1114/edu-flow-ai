package com.yuy.eduflow.allocation;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.conflict.ConflictDiagnosis;
import com.yuy.eduflow.ml.MlFeedbackEvent;
import com.yuy.eduflow.ml.MlFeedbackEventMarkRequest;
import com.yuy.eduflow.ml.MlFeedbackEventService;
import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.teachingtask.TeachingTaskMapper;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;
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
	private final TeachingTaskMapper teachingTaskMapper;
	private final ObjectMapper objectMapper = new ObjectMapper();

	public AllocationSchemeController(
		AllocationSchemeService allocationSchemeService,
		AllocationItemService allocationItemService,
		AllocationSchemeConfirmService allocationSchemeConfirmService,
		AllocationItemAdjustmentLogMapper adjustmentLogMapper,
		MlFeedbackEventService feedbackEventService,
		AllocationTaskService allocationTaskService,
		AllocationTemplateMapper allocationTemplateMapper,
		TeachingTaskMapper teachingTaskMapper
	) {
		this.allocationSchemeService = allocationSchemeService;
		this.allocationItemService = allocationItemService;
		this.allocationSchemeConfirmService = allocationSchemeConfirmService;
		this.adjustmentLogMapper = adjustmentLogMapper;
		this.feedbackEventService = feedbackEventService;
		this.allocationTaskService = allocationTaskService;
		this.allocationTemplateMapper = allocationTemplateMapper;
		this.teachingTaskMapper = teachingTaskMapper;
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
				view.setTeachingTaskId(e.getTeachingTaskId());
				view.setCourseName(e.getCourseName());
				view.setTeacherName(e.getTeacherName() != null && !e.getTeacherName().isBlank() ? e.getTeacherName() : null);
				view.setClassGroupName(e.getClassName());
				view.setClassroomId(e.getClassroomId());
				view.setClassroomName(e.getClassroomName());
				view.setWeekNumber(e.getWeekNumber());
				view.setDayOfWeek(e.getDayOfWeek());
				view.setPeriodIndex(e.getPeriodIndex());
				view.setValid(true);
				allItems.add(view);
			}
		}
		markV35Conflicts(allItems);
		return allItems;
	}

	private void markV35Conflicts(List<AllocationItemView> items) {
		Map<Long, List<String>> messages = new LinkedHashMap<>();
		collectOccupancyConflicts(items, "教师冲突", AllocationItemView::getTeacherName, messages);
		collectOccupancyConflicts(items, "班级冲突", AllocationItemView::getClassGroupName, messages);
		collectOccupancyConflicts(items, "教室冲突", AllocationItemView::getClassroomName, messages);
		collectTeachingTaskHourConflicts(items, messages);
		for (AllocationItemView item : items) {
			List<String> itemMessages = messages.get(item.getId());
			if (itemMessages == null || itemMessages.isEmpty()) {
				item.setValid(true);
				item.setConflictMessage(null);
			} else {
				item.setValid(false);
				item.setConflictMessage(String.join("；", itemMessages));
			}
		}
	}

	private void collectOccupancyConflicts(
		List<AllocationItemView> items,
		String label,
		java.util.function.Function<AllocationItemView, String> resourceExtractor,
		Map<Long, List<String>> messages
	) {
		Map<String, List<AllocationItemView>> buckets = new LinkedHashMap<>();
		for (AllocationItemView item : items) {
			String resource = resourceExtractor.apply(item);
			if (resource == null || resource.isBlank()) continue;
			String key = String.join("|", resource, String.valueOf(item.getWeekNumber()), String.valueOf(item.getDayOfWeek()), String.valueOf(item.getPeriodIndex()));
			buckets.computeIfAbsent(key, ignored -> new ArrayList<>()).add(item);
		}
		for (List<AllocationItemView> bucket : buckets.values()) {
			if (bucket.size() <= 1) continue;
			AllocationItemView first = bucket.get(0);
			String detail = "%s：%s 在第%d周 周%d 第%d节重复安排 %d 条".formatted(
				label,
				resourceExtractor.apply(first),
				first.getWeekNumber(),
				first.getDayOfWeek(),
				first.getPeriodIndex(),
				bucket.size()
			);
			for (AllocationItemView item : bucket) {
				messages.computeIfAbsent(item.getId(), ignored -> new ArrayList<>()).add(detail);
			}
		}
	}

	private void collectTeachingTaskHourConflicts(List<AllocationItemView> items, Map<Long, List<String>> messages) {
		Set<Long> taskIds = items.stream().map(AllocationItemView::getTeachingTaskId).filter(Objects::nonNull).collect(Collectors.toSet());
		if (taskIds.isEmpty()) return;
		String ids = taskIds.stream().map(String::valueOf).collect(Collectors.joining(","));
		Map<Long, Integer> expectedHours = new HashMap<>();
		for (TeachingTask task : teachingTaskMapper.findHoursByIds(ids)) {
			expectedHours.put(task.getId(), task.getTotalHours());
		}
		Map<Long, Long> actualHours = items.stream()
			.filter(item -> item.getTeachingTaskId() != null)
			.collect(Collectors.groupingBy(AllocationItemView::getTeachingTaskId, Collectors.counting()));
		for (AllocationItemView item : items) {
			Long taskId = item.getTeachingTaskId();
			if (taskId == null || !expectedHours.containsKey(taskId)) continue;
			int expected = expectedHours.getOrDefault(taskId, 0);
			long actual = actualHours.getOrDefault(taskId, 0L) * 2;
			if (expected > 0 && actual != expected) {
				messages.computeIfAbsent(item.getId(), ignored -> new ArrayList<>()).add(
					"课时不匹配：教学任务#%d 应排%d课时，当前展开%d课时".formatted(taskId, expected, actual)
				);
			}
		}
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
