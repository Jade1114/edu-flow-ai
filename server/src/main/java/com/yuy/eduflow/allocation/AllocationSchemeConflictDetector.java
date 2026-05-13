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

	private final AllocationItemMapper allocationItemMapper;
	private final com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper;
	private final TimeSlotService timeSlotService;

	public AllocationSchemeConflictDetector(
		AllocationItemMapper allocationItemMapper,
		com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper,
		TimeSlotService timeSlotService
	) {
		this.allocationItemMapper = allocationItemMapper;
		this.teachingTaskMapper = teachingTaskMapper;
		this.timeSlotService = timeSlotService;
	}

	public List<AllocationConflictViolation> detect(List<AllocationItem> items) {
		if (items == null || items.isEmpty()) {
			return List.of();
		}
		// 预加载所有教学任务 + 时间段
		Map<Long, TeachingTaskDetail> taskDetails = loadTaskDetails(items);
		Map<Long, Integer> timeSlotWeekMap = loadTimeSlotWeekMap();
		List<AllocationConflictViolation> violations = new ArrayList<>();

		detectConflicts(items, item -> teacherKey(item, taskDetails), (item, group) -> teacherViolation(item, group, taskDetails), violations);
		detectConflicts(items, item -> classGroupKey(item, taskDetails), (item, group) -> classGroupViolation(item, group, taskDetails), violations);
		detectConflicts(items, item -> classroomKey(item), this::classroomViolation, violations);
		detectWorkloadViolations(items, taskDetails, timeSlotWeekMap, violations);

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
		return "发现 " + violations.size() + " 条冲突记录：" + String.join("，", parts);
	}

	private Map<Long, TeachingTaskDetail> loadTaskDetails(List<AllocationItem> items) {
		Map<Long, TeachingTaskDetail> details = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			Long taskId = item.getTeachingTaskId();
			if (taskId == null || details.containsKey(taskId)) continue;
			var task = teachingTaskMapper.findWithDetails(taskId);
			if (task == null) continue;
			int totalStudents = task.getClassGroups() == null ? 0
				: task.getClassGroups().stream().mapToInt(cg -> cg.getStudentCount() != null ? cg.getStudentCount() : 0).sum();
			details.put(taskId, new TeachingTaskDetail(task, totalStudents));
		}
		return details;
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

	private ConflictKey classGroupKey(AllocationItem item, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		if (detail == null || detail.task().getClassGroups() == null || detail.task().getClassGroups().isEmpty()) return null;
		// 用第一个班级作为代表，后续 violation 中会列出所有班级
		Long firstClassGroupId = detail.task().getClassGroups().get(0).getId();
		return new ConflictKey(firstClassGroupId, item.getTimeSlotId());
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

	private AllocationConflictViolation classGroupViolation(AllocationItem item, List<AllocationItem> group, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		String classNames = detail != null && detail.task().getClassGroups() != null
			? detail.task().getClassGroups().stream().map(cg -> cg.getName()).collect(Collectors.joining(","))
			: "班级";
		return new AllocationConflictViolation(
			item.getId(),
			CLASS_GROUP_TIME,
			"班级时间冲突：" + classNames + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			null, null, null, item.getTimeSlotId()
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
