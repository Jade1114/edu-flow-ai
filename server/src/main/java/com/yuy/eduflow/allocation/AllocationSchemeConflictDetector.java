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
import org.springframework.stereotype.Component;

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
		if ((items == null || items.isEmpty()) && allocationTaskId == null) {
			return List.of();
		}
		List<AllocationItem> safeItems = items == null ? List.of() : items;
		// 预加载所有教学任务 + 时间段
		Map<Long, TeachingTaskDetail> taskDetails = loadTaskDetails(safeItems, allocationTaskId);
		Map<Long, Integer> timeSlotWeekMap = loadTimeSlotWeekMap();
		List<AllocationConflictViolation> violations = new ArrayList<>();

		detectConflicts(safeItems, item -> teacherKey(item, taskDetails), (item, group) -> teacherViolation(item, group, taskDetails), violations);
		detectClassGroupConflicts(safeItems, taskDetails, violations);
		detectConflicts(safeItems, item -> classroomKey(item), this::classroomViolation, violations);
		detectWorkloadViolations(safeItems, taskDetails, timeSlotWeekMap, violations);
		detectTeachingTaskHourViolations(safeItems, taskDetails, violations);

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

	private void detectWorkloadViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		Map<Long, Integer> timeSlotWeekMap,
		List<AllocationConflictViolation> violations
	) {
		// 按 (teacherId, weekNumber) 分组，统计每周总课时
		Map<String, List<AllocationItem>> workloadGroups = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
			if (detail == null || detail.task().getPrimaryTeacherId() == null) continue;
			Integer weekNumber = timeSlotWeekMap.get(item.getTimeSlotId());
			if (weekNumber == null) continue;
			String workloadKey = detail.task().getPrimaryTeacherId() + ":" + weekNumber;
			workloadGroups.computeIfAbsent(workloadKey, ignored -> new ArrayList<>()).add(item);
		}

		// 检测每周课时是否超过教师上限
		for (Map.Entry<String, List<AllocationItem>> entry : workloadGroups.entrySet()) {
			List<AllocationItem> group = entry.getValue();
			AllocationItem firstItem = group.get(0);
			TeachingTaskDetail detail = taskDetails.get(firstItem.getTeachingTaskId());
			if (detail == null) continue;
			Teacher teacher = detail.task().getPrimaryTeacher();
			if (teacher == null || teacher.getMaxWeeklyHours() == null) continue;

			int totalHours = group.size() * 2; // 每个 timeSlot = 2 课时
			if (totalHours <= teacher.getMaxWeeklyHours()) continue;

			int weekNumber = timeSlotWeekMap.get(firstItem.getTimeSlotId());
			String teacherName = teacher.getName();
			for (AllocationItem item : group) {
				violations.add(new AllocationConflictViolation(
					item.getId(),
					TEACHER_WORKLOAD,
					"教师工作量冲突：" + teacherName + " 第 " + weekNumber + " 周共 " + totalHours
						+ " 课时，超过最大周课时 " + teacher.getMaxWeeklyHours() + " 课时",
					teacher.getId(), null, null, item.getTimeSlotId()
				));
			}
		}
	}

	private void detectTeachingTaskHourViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		List<AllocationConflictViolation> violations
	) {
		Map<Long, List<AllocationItem>> itemsByTaskId = items.stream()
			.filter(item -> item.getTeachingTaskId() != null)
			.collect(Collectors.groupingBy(AllocationItem::getTeachingTaskId, LinkedHashMap::new, Collectors.toList()));

		for (TeachingTaskDetail detail : taskDetails.values()) {
			TeachingTask task = detail.task();
			if (task.getId() == null || task.getTotalHours() == null) continue;
			List<AllocationItem> taskItems = itemsByTaskId.getOrDefault(task.getId(), List.of());
			int actualHours = taskItems.size() * 2;
			int expectedHours = task.getTotalHours();
			if (actualHours == expectedHours) continue;

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
	}

	private void detectConflicts(
		List<AllocationItem> items,
		Function<AllocationItem, ConflictKey> keyExtractor,
		ConflictViolationFactory violationFactory,
		List<AllocationConflictViolation> violations
	) {
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
	}

	private ConflictKey teacherKey(AllocationItem item, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		if (detail == null || detail.task().getPrimaryTeacherId() == null) return null;
		return new ConflictKey(detail.task().getPrimaryTeacherId(), item.getTimeSlotId());
	}

	private void detectClassGroupConflicts(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		List<AllocationConflictViolation> violations
	) {
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
			.forEach(entry -> entry.getValue().forEach(item -> violations.add(classGroupViolation(item, entry.getValue(), entry.getKey().resourceId(), taskDetails))));
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
			null, null, item.getTimeSlotId()
		);
	}

	private AllocationConflictViolation classGroupViolation(AllocationItem item, List<AllocationItem> group, Long classGroupId, Map<Long, TeachingTaskDetail> taskDetails) {
		String className = taskDetails.values().stream()
			.filter(detail -> detail.task().getClassGroups() != null)
			.flatMap(detail -> detail.task().getClassGroups().stream())
			.filter(classGroup -> classGroupId.equals(classGroup.getId()))
			.map(classGroup -> classGroup.getName())
			.findFirst()
			.orElse("班级" + classGroupId);
		return new AllocationConflictViolation(
			item.getId(),
			CLASS_GROUP_TIME,
			"班级时间冲突：" + className + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			null, classGroupId, null, item.getTimeSlotId()
		);
	}

	private AllocationConflictViolation classroomViolation(AllocationItem item, List<AllocationItem> group) {
		return new AllocationConflictViolation(
			item.getId(),
			CLASSROOM_TIME,
			"教室时间冲突：教室ID " + item.getClassroomId() + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复占用，涉及明细ID：" + itemIds(group),
			null, null, item.getClassroomId(), item.getTimeSlotId()
		);
	}

	private String itemIds(List<AllocationItem> items) {
		return items.stream()
			.map(item -> item.getId() == null ? "未落库" : item.getId().toString())
			.collect(Collectors.joining(", "));
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
