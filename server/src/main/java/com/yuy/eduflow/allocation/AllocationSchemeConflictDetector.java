package com.yuy.eduflow.allocation;

import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class AllocationSchemeConflictDetector {
	static final String TEACHER_TIME = "TEACHER_TIME";
	static final String CLASS_GROUP_TIME = "CLASS_GROUP_TIME";
	static final String CLASSROOM_TIME = "CLASSROOM_TIME";
	static final String TEACHER_WORKLOAD = "TEACHER_WORKLOAD";
	static final String TEACHING_TASK_HOURS = "TEACHING_TASK_HOURS";

	private final AllocationItemMapper allocationItemMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper;
	private final TimeSlotService timeSlotService;

	public AllocationSchemeConflictDetector(
		AllocationItemMapper allocationItemMapper,
		AllocationTaskMapper allocationTaskMapper,
		com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper,
		TimeSlotService timeSlotService
	) {
		this.allocationItemMapper = allocationItemMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.teachingTaskMapper = teachingTaskMapper;
		this.timeSlotService = timeSlotService;
	}

	public List<AllocationConflictViolation> detect(List<AllocationItem> items) {
		return detect(items, null);
	}

	public List<AllocationConflictViolation> detect(List<AllocationItem> items, Long allocationTaskId) {
		long startedAt = System.nanoTime();
		if ((items == null || items.isEmpty()) && allocationTaskId == null) {
			return List.of();
		}
		List<AllocationItem> safeItems = items == null ? List.of() : items;
		// 预加载所有教学任务 + 时间段
		long preloadStartedAt = System.nanoTime();
		Map<Long, TeachingTaskDetail> taskDetails = loadTaskDetails(safeItems, allocationTaskId);
		Map<Long, Integer> timeSlotWeekMap = loadTimeSlotWeekMap();
		log.info("Conflict detector preload: items={} allocationTaskId={} taskDetails={} timeSlots={} elapsedMs={}",
			safeItems.size(), allocationTaskId, taskDetails.size(), timeSlotWeekMap.size(), elapsedMs(preloadStartedAt));
		List<AllocationConflictViolation> violations = new ArrayList<>();

		long teacherStartedAt = System.nanoTime();
		int teacherViolations = detectConflicts(safeItems, item -> teacherKey(item, taskDetails), (item, group) -> teacherViolation(item, group, taskDetails), violations);
		log.info("Conflict detector teacher-time: violations={} elapsedMs={}", teacherViolations, elapsedMs(teacherStartedAt));
		long classStartedAt = System.nanoTime();
		int classViolations = detectClassGroupConflicts(safeItems, taskDetails, violations);
		log.info("Conflict detector class-time: violations={} elapsedMs={}", classViolations, elapsedMs(classStartedAt));
		long classroomStartedAt = System.nanoTime();
		int classroomViolations = detectConflicts(safeItems, item -> classroomKey(item), this::classroomViolation, violations);
		log.info("Conflict detector classroom-time: violations={} elapsedMs={}", classroomViolations, elapsedMs(classroomStartedAt));
		long workloadStartedAt = System.nanoTime();
		int workloadViolations = detectWorkloadViolations(safeItems, taskDetails, timeSlotWeekMap, violations);
		log.info("Conflict detector workload: violations={} elapsedMs={}", workloadViolations, elapsedMs(workloadStartedAt));
		long hoursStartedAt = System.nanoTime();
		int hourViolations = detectTeachingTaskHourViolations(safeItems, taskDetails, violations);
		log.info("Conflict detector task-hours: violations={} elapsedMs={}", hourViolations, elapsedMs(hoursStartedAt));
		log.info(
			"Conflict detector done: items={} taskDetails={} totalViolations={} elapsedMs={} breakdown={teacher:{},class:{},classroom:{},workload:{},hours:{}}",
			safeItems.size(), taskDetails.size(), violations.size(), elapsedMs(startedAt),
			teacherViolations, classViolations, classroomViolations, workloadViolations, hourViolations
		);

		return violations;
	}

	public String summarize(List<AllocationConflictViolation> violations) {
		if (violations == null || violations.isEmpty()) {
			return "无明显冲突";
		}
		Map<String, Long> counts = violations.stream()
			.collect(Collectors.groupingBy(
				AllocationConflictViolation::conflictType,
				LinkedHashMap::new,
				Collectors.counting()
			));
		List<String> parts = new ArrayList<>();
		appendSummary(parts, counts, TEACHER_TIME, "教师时间冲突");
		appendSummary(parts, counts, CLASS_GROUP_TIME, "班级时间冲突");
		appendSummary(parts, counts, CLASSROOM_TIME, "教室时间冲突");
		appendSummary(parts, counts, TEACHER_WORKLOAD, "教师工作量冲突");
		appendSummary(parts, counts, TEACHING_TASK_HOURS, "教学任务课时不匹配");
		return "发现 " + violations.size() + " 条冲突记录：" + String.join("，", parts);
	}

	private Map<Long, TeachingTaskDetail> loadTaskDetails(List<AllocationItem> items, Long allocationTaskId) {
		Map<Long, TeachingTaskDetail> details = new LinkedHashMap<>();
		if (allocationTaskId != null) {
			for (AllocationTaskTeachingTaskResult taskResult : allocationTaskMapper.findTeachingTasks(allocationTaskId)) {
				loadTaskDetail(taskResult.getId(), details);
			}
		}
		for (AllocationItem item : items) {
			loadTaskDetail(item.getTeachingTaskId(), details);
		}
		return details;
	}

	private void loadTaskDetail(Long taskId, Map<Long, TeachingTaskDetail> details) {
		if (taskId == null || details.containsKey(taskId)) return;
		var task = teachingTaskMapper.findWithDetails(taskId);
		if (task == null) return;
		int totalStudents = task.getClassGroups() == null ? 0
			: task.getClassGroups().stream().mapToInt(cg -> cg.getStudentCount() != null ? cg.getStudentCount() : 0).sum();
		details.put(taskId, new TeachingTaskDetail(task, totalStudents));
	}

	private Map<Long, Integer> loadTimeSlotWeekMap() {
		return timeSlotService.findAll(null, null).stream()
			.collect(Collectors.toMap(TimeSlot::getId, TimeSlot::getWeekNumber));
	}

	private int detectWorkloadViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		Map<Long, Integer> timeSlotWeekMap,
		List<AllocationConflictViolation> violations
	) {
		log.info("  [workload] start: items={} taskDetails={}" , items.size(), taskDetails.size());
		log.info("  [workload] skipped: max_weekly_hours 字段已移除，暂不检测教师工作量");
		int before = violations.size();

		// max_weekly_hours 字段已移除（2026-06-01 schema 清理）
		// 工作量冲突检测暂时跳过，后续在 teacher_profile 中重新实现
		return violations.size() - before;
	}

	private int detectTeachingTaskHourViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		List<AllocationConflictViolation> violations
	) {
		log.info("  [task-hours] start: items={} taskDetails={}", items.size(), taskDetails.size());
		int before = violations.size();
		Map<Long, List<AllocationItem>> itemsByTaskId = items.stream()
			.filter(item -> item.getTeachingTaskId() != null)
			.collect(Collectors.groupingBy(AllocationItem::getTeachingTaskId, LinkedHashMap::new, Collectors.toList()));
		log.info("  [task-hours] grouped: uniqueTasks={}", itemsByTaskId.size());

		int checked = 0, matched = 0, mismatched = 0;
		for (TeachingTaskDetail detail : taskDetails.values()) {
			TeachingTask task = detail.task();
			if (task.getId() == null || task.getTotalHours() == null) continue;
			List<AllocationItem> taskItems = itemsByTaskId.getOrDefault(task.getId(), List.of());
			int actualHours = taskItems.size() * 2;
			int expectedHours = task.getTotalHours();
			checked++;
			if (actualHours == expectedHours) { matched++; continue; }
			mismatched++;

			String courseName = task.getCourse() != null && task.getCourse().getName() != null
				? task.getCourse().getName()
				: "教学任务" + task.getId();
			int diff = expectedHours - actualHours;
			String message = "课程《" + courseName + "》计划 " + expectedHours + " 课时，实际只排了 "
				+ actualHours + " 课时（缺 " + diff + " 课时），请返回方案调整页面增加排课片段";
			if (taskItems.isEmpty()) {
				violations.add(new AllocationConflictViolation(
					null, TEACHING_TASK_HOURS, message, task.getPrimaryTeacherId(), null, null, null,
					task.getId(), courseName, expectedHours, actualHours
				));
			} else {
				for (AllocationItem item : taskItems) {
					violations.add(new AllocationConflictViolation(
						item.getId(), TEACHING_TASK_HOURS, message, task.getPrimaryTeacherId(), null, item.getClassroomId(), item.getTimeSlotId(),
						task.getId(), courseName, expectedHours, actualHours
					));
				}
			}
		}
		log.info("  [task-hours] done: checked={} matched={} mismatched={} violations={}",
			checked, matched, mismatched, violations.size() - before);
		return violations.size() - before;
	}

	private int detectConflicts(
		List<AllocationItem> items,
		Function<AllocationItem, ConflictKey> keyExtractor,
		ConflictViolationFactory violationFactory,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		Map<ConflictKey, List<AllocationItem>> groupedItems = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			ConflictKey key = keyExtractor.apply(item);
			if (key == null || key.resourceId() == null || key.timeSlotId() == null) {
				continue;
			}
			groupedItems.computeIfAbsent(key, ignored -> new ArrayList<>()).add(item);
		}
		groupedItems.values().stream()
			.filter(group -> group.size() > 1)
			.forEach(group -> group.forEach(item -> violations.add(violationFactory.create(item, group))));
		return violations.size() - before;
	}

	private ConflictKey teacherKey(AllocationItem item, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		if (detail == null || detail.task().getPrimaryTeacherId() == null) return null;
		return new ConflictKey(detail.task().getPrimaryTeacherId(), item.getTimeSlotId());
	}

	private int detectClassGroupConflicts(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		Map<Long, String> classGroupNames = taskDetails.values().stream()
			.filter(detail -> detail.task().getClassGroups() != null)
			.flatMap(detail -> detail.task().getClassGroups().stream())
			.filter(classGroup -> classGroup.getId() != null)
			.collect(Collectors.toMap(
				classGroup -> classGroup.getId(),
				classGroup -> classGroup.getName() != null ? classGroup.getName() : "班级" + classGroup.getId(),
				(existing, replacement) -> existing,
				LinkedHashMap::new
			));
		Map<ConflictKey, List<AllocationItem>> groupedItems = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
			if (detail == null || detail.task().getClassGroups() == null || detail.task().getClassGroups().isEmpty()) continue;
			for (var classGroup : detail.task().getClassGroups()) {
				if (classGroup.getId() == null || item.getTimeSlotId() == null) continue;
				ConflictKey key = new ConflictKey(classGroup.getId(), item.getTimeSlotId());
				groupedItems.computeIfAbsent(key, ignored -> new ArrayList<>()).add(item);
			}
		}
		groupedItems.entrySet().stream()
			.filter(entry -> entry.getValue().size() > 1)
			.forEach(entry -> entry.getValue().forEach(item -> violations.add(classGroupViolation(item, entry.getValue(), entry.getKey().resourceId(), classGroupNames))));
		return violations.size() - before;
	}

	private ConflictKey classroomKey(AllocationItem item) {
		return new ConflictKey(item.getClassroomId(), item.getTimeSlotId());
	}

	private AllocationConflictViolation teacherViolation(AllocationItem item, List<AllocationItem> group, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		String teacherName = detail != null && detail.task().getPrimaryTeacher() != null
			? detail.task().getPrimaryTeacher().getName()
			: "教师" + detail.task().getPrimaryTeacherId();
		return new AllocationConflictViolation(
			item.getId(),
			TEACHER_TIME,
			"教师时间冲突：" + teacherName + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			detail != null ? detail.task().getPrimaryTeacherId() : null,
			null, null, item.getTimeSlotId(),
			null, null, null, null
		);
	}

	private AllocationConflictViolation classGroupViolation(AllocationItem item, List<AllocationItem> group, Long classGroupId, Map<Long, String> classGroupNames) {
		String className = classGroupNames.getOrDefault(classGroupId, "班级" + classGroupId);
		return new AllocationConflictViolation(
			item.getId(),
			CLASS_GROUP_TIME,
			"班级时间冲突：" + className + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			null, classGroupId, null, item.getTimeSlotId(),
			null, null, null, null
		);
	}

	private AllocationConflictViolation classroomViolation(AllocationItem item, List<AllocationItem> group) {
		return new AllocationConflictViolation(
			item.getId(),
			CLASSROOM_TIME,
			"教室时间冲突：教室ID " + item.getClassroomId() + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复占用，涉及明细ID：" + itemIds(group),
			null, null, item.getClassroomId(), item.getTimeSlotId(),
			null, null, null, null
		);
	}

	private String itemIds(List<AllocationItem> items) {
		return items.stream()
			.map(item -> item.getId() == null ? "未落库" : item.getId().toString())
			.collect(Collectors.joining(", "));
	}

	private long elapsedMs(long startedAtNanos) {
		return Math.round((System.nanoTime() - startedAtNanos) / 1_000_000.0);
	}

	private void appendSummary(List<String> parts, Map<String, Long> counts, String type, String label) {
		Long count = counts.get(type);
		if (count != null && count > 0) {
			parts.add(label + " " + count + " 条");
		}
	}

	private record ConflictKey(Long resourceId, Long timeSlotId) {
	}

	private record TeachingTaskDetail(TeachingTask task, int totalStudents) {
	}

	@FunctionalInterface
	private interface ConflictViolationFactory {
		AllocationConflictViolation create(AllocationItem item, List<AllocationItem> group);
	}
}
