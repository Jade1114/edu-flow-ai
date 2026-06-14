package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomMapper;
import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
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
	static final String CLASSROOM_CAPACITY = "CLASSROOM_CAPACITY";
	static final String CLASSROOM_TYPE = "CLASSROOM_TYPE";
	static final String INVALID_REFERENCE = "INVALID_REFERENCE";
	static final String DUPLICATE_TASK_TIME = "DUPLICATE_TASK_TIME";
	static final String TEACHER_WORKLOAD = "TEACHER_WORKLOAD";
	static final String TEACHING_TASK_HOURS = "TEACHING_TASK_HOURS";

	private final AllocationItemMapper allocationItemMapper;
	private final AllocationTaskMapper allocationTaskMapper;
	private final com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper;
	private final ClassroomMapper classroomMapper;
	private final TimeSlotService timeSlotService;

	public AllocationSchemeConflictDetector(
		AllocationItemMapper allocationItemMapper,
		AllocationTaskMapper allocationTaskMapper,
		com.yuy.eduflow.teachingtask.TeachingTaskMapper teachingTaskMapper,
		ClassroomMapper classroomMapper,
		TimeSlotService timeSlotService
	) {
		this.allocationItemMapper = allocationItemMapper;
		this.allocationTaskMapper = allocationTaskMapper;
		this.teachingTaskMapper = teachingTaskMapper;
		this.classroomMapper = classroomMapper;
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
		Set<Long> expectedTaskIds = new LinkedHashSet<>();
		Map<Long, TeachingTaskDetail> taskDetails = loadTaskDetails(safeItems, allocationTaskId, expectedTaskIds);
		Map<Long, Classroom> classroomMap = loadClassrooms(safeItems);
		Map<Long, Integer> timeSlotWeekMap = loadTimeSlotWeekMap();
		log.info("Conflict detector preload: items={} allocationTaskId={} expectedTasks={} taskDetails={} classrooms={} timeSlots={} elapsedMs={}",
			safeItems.size(), allocationTaskId, expectedTaskIds.size(), taskDetails.size(), classroomMap.size(), timeSlotWeekMap.size(), elapsedMs(preloadStartedAt));
		List<AllocationConflictViolation> violations = new ArrayList<>();

		long referenceStartedAt = System.nanoTime();
		int referenceViolations = detectInvalidReferences(safeItems, allocationTaskId, expectedTaskIds, taskDetails, classroomMap, timeSlotWeekMap, violations);
		log.info("Conflict detector references: violations={} elapsedMs={}", referenceViolations, elapsedMs(referenceStartedAt));
		long duplicateTaskStartedAt = System.nanoTime();
		int duplicateTaskViolations = detectDuplicateTaskTimeViolations(safeItems, taskDetails, violations);
		log.info("Conflict detector duplicate-task-time: violations={} elapsedMs={}", duplicateTaskViolations, elapsedMs(duplicateTaskStartedAt));
		long teacherStartedAt = System.nanoTime();
		int teacherViolations = detectConflicts(safeItems, item -> teacherKey(item, taskDetails), (item, group) -> teacherViolation(item, group, taskDetails), violations);
		log.info("Conflict detector teacher-time: violations={} elapsedMs={}", teacherViolations, elapsedMs(teacherStartedAt));
		long classStartedAt = System.nanoTime();
		int classViolations = detectClassGroupConflicts(safeItems, taskDetails, violations);
		log.info("Conflict detector class-time: violations={} elapsedMs={}", classViolations, elapsedMs(classStartedAt));
		long classroomStartedAt = System.nanoTime();
		int classroomViolations = detectConflicts(safeItems, item -> classroomKey(item), this::classroomViolation, violations);
		log.info("Conflict detector classroom-time: violations={} elapsedMs={}", classroomViolations, elapsedMs(classroomStartedAt));
		long roomCapacityStartedAt = System.nanoTime();
		int roomCapacityViolations = detectClassroomCapacityViolations(safeItems, taskDetails, classroomMap, violations);
		log.info("Conflict detector classroom-capacity: violations={} elapsedMs={}", roomCapacityViolations, elapsedMs(roomCapacityStartedAt));
		long roomTypeStartedAt = System.nanoTime();
		int roomTypeViolations = detectClassroomTypeViolations(safeItems, taskDetails, classroomMap, violations);
		log.info("Conflict detector classroom-type: violations={} elapsedMs={}", roomTypeViolations, elapsedMs(roomTypeStartedAt));
		long workloadStartedAt = System.nanoTime();
		int workloadViolations = detectWorkloadViolations(safeItems, taskDetails, timeSlotWeekMap, violations);
		log.info("Conflict detector workload: violations={} elapsedMs={}", workloadViolations, elapsedMs(workloadStartedAt));
		long hoursStartedAt = System.nanoTime();
		int hourViolations = detectTeachingTaskHourViolations(safeItems, taskDetails, violations);
		log.info("Conflict detector task-hours: violations={} elapsedMs={}", hourViolations, elapsedMs(hoursStartedAt));
		log.info(
			"Conflict detector done: items={} taskDetails={} totalViolations={} elapsedMs={} breakdown={reference:{},duplicateTask:{},teacher:{},class:{},classroom:{},capacity:{},type:{},workload:{},hours:{}}",
			safeItems.size(), taskDetails.size(), violations.size(), elapsedMs(startedAt),
			referenceViolations, duplicateTaskViolations, teacherViolations, classViolations, classroomViolations,
			roomCapacityViolations, roomTypeViolations, workloadViolations, hourViolations
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
		appendSummary(parts, counts, CLASSROOM_CAPACITY, "教室容量不足");
		appendSummary(parts, counts, CLASSROOM_TYPE, "教室类型不匹配");
		appendSummary(parts, counts, INVALID_REFERENCE, "无效资源引用");
		appendSummary(parts, counts, DUPLICATE_TASK_TIME, "教学任务重复时间片");
		appendSummary(parts, counts, TEACHER_WORKLOAD, "教师工作量冲突");
		appendSummary(parts, counts, TEACHING_TASK_HOURS, "教学任务课时不匹配");
		return "发现 " + violations.size() + " 条冲突记录：" + String.join("，", parts);
	}

	private Map<Long, TeachingTaskDetail> loadTaskDetails(List<AllocationItem> items, Long allocationTaskId, Set<Long> expectedTaskIds) {
		Map<Long, TeachingTaskDetail> details = new LinkedHashMap<>();
		if (allocationTaskId != null) {
			for (AllocationTaskTeachingTaskResult taskResult : allocationTaskMapper.findTeachingTasks(allocationTaskId)) {
				if (taskResult.getId() != null) {
					expectedTaskIds.add(taskResult.getId());
				}
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

	private Map<Long, Classroom> loadClassrooms(List<AllocationItem> items) {
		Map<Long, Classroom> classrooms = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			Long classroomId = item.getClassroomId();
			if (classroomId == null || classrooms.containsKey(classroomId)) continue;
			Classroom classroom = classroomMapper.findById(classroomId);
			if (classroom != null) {
				classrooms.put(classroomId, classroom);
			}
		}
		return classrooms;
	}

	private int detectInvalidReferences(
		List<AllocationItem> items,
		Long allocationTaskId,
		Set<Long> expectedTaskIds,
		Map<Long, TeachingTaskDetail> taskDetails,
		Map<Long, Classroom> classroomMap,
		Map<Long, Integer> timeSlotWeekMap,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		for (AllocationItem item : items) {
			if (item.getTeachingTaskId() == null) {
				violations.add(invalidReferenceViolation(item, "教学任务为空"));
			} else if (!taskDetails.containsKey(item.getTeachingTaskId())) {
				violations.add(invalidReferenceViolation(item, "教学任务不存在"));
			} else if (allocationTaskId != null && !expectedTaskIds.contains(item.getTeachingTaskId())) {
				violations.add(invalidReferenceViolation(item, "教学任务未绑定到当前排课任务"));
			}
			if (item.getTimeSlotId() == null || !timeSlotWeekMap.containsKey(item.getTimeSlotId())) {
				violations.add(invalidReferenceViolation(item, "时间段不存在"));
			}
			if (item.getClassroomId() == null || !classroomMap.containsKey(item.getClassroomId())) {
				violations.add(invalidReferenceViolation(item, "教室不存在"));
			}
		}
		return violations.size() - before;
	}

	private int detectDuplicateTaskTimeViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		Map<ConflictKey, List<AllocationItem>> groupedItems = new LinkedHashMap<>();
		for (AllocationItem item : items) {
			if (item.getTeachingTaskId() == null || item.getTimeSlotId() == null) continue;
			ConflictKey key = new ConflictKey(item.getTeachingTaskId(), item.getTimeSlotId());
			groupedItems.computeIfAbsent(key, ignored -> new ArrayList<>()).add(item);
		}
		groupedItems.entrySet().stream()
			.filter(entry -> entry.getValue().size() > 1)
			.forEach(entry -> entry.getValue().forEach(item -> violations.add(duplicateTaskTimeViolation(item, entry.getValue(), taskDetails))));
		return violations.size() - before;
	}

	private int detectClassroomCapacityViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		Map<Long, Classroom> classroomMap,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		for (AllocationItem item : items) {
			TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
			Classroom classroom = classroomMap.get(item.getClassroomId());
			if (detail == null || classroom == null || classroom.getCapacity() == null) continue;
			if (detail.totalStudents() <= classroom.getCapacity()) continue;
			violations.add(classroomCapacityViolation(item, detail, classroom));
		}
		return violations.size() - before;
	}

	private int detectClassroomTypeViolations(
		List<AllocationItem> items,
		Map<Long, TeachingTaskDetail> taskDetails,
		Map<Long, Classroom> classroomMap,
		List<AllocationConflictViolation> violations
	) {
		int before = violations.size();
		for (AllocationItem item : items) {
			TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
			Classroom classroom = classroomMap.get(item.getClassroomId());
			if (detail == null || classroom == null) continue;
			String requiredType = normalize(detail.task().getRequiredRoomType());
			String classroomType = normalize(classroom.getClassroomType());
			if (requiredType == null || classroomType == null || requiredType.equals(classroomType)) continue;
			violations.add(classroomTypeViolation(item, detail, classroom, requiredType, classroomType));
		}
		return violations.size() - before;
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
			String diffText = diff > 0 ? "缺 " + diff + " 课时" : "多排 " + Math.abs(diff) + " 课时";
			String actionText = diff > 0 ? "增加排课片段" : "减少排课片段";
			String message = "课程《" + courseName + "》计划 " + expectedHours + " 课时，实际排了 "
				+ actualHours + " 课时（" + diffText + "），请返回方案调整页面" + actionText;
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

	private AllocationConflictViolation invalidReferenceViolation(AllocationItem item, String reason) {
		return new AllocationConflictViolation(
			item.getId(),
			INVALID_REFERENCE,
			"无效资源引用：" + reason + "，明细ID " + (item.getId() == null ? "未落库" : item.getId())
				+ "，教学任务ID " + item.getTeachingTaskId() + "，教室ID " + item.getClassroomId()
				+ "，时间段ID " + item.getTimeSlotId(),
			null, null, item.getClassroomId(), item.getTimeSlotId(),
			item.getTeachingTaskId(), null, null, null
		);
	}

	private AllocationConflictViolation duplicateTaskTimeViolation(AllocationItem item, List<AllocationItem> group, Map<Long, TeachingTaskDetail> taskDetails) {
		TeachingTaskDetail detail = taskDetails.get(item.getTeachingTaskId());
		String courseName = courseName(detail, item.getTeachingTaskId());
		return new AllocationConflictViolation(
			item.getId(),
			DUPLICATE_TASK_TIME,
			"教学任务重复时间片：课程《" + courseName + "》在时间段ID " + item.getTimeSlotId()
				+ " 出现多个排课片段，涉及明细ID：" + itemIds(group),
			detail != null ? detail.task().getPrimaryTeacherId() : null,
			null, item.getClassroomId(), item.getTimeSlotId(),
			item.getTeachingTaskId(), courseName, null, null
		);
	}

	private AllocationConflictViolation classroomCapacityViolation(AllocationItem item, TeachingTaskDetail detail, Classroom classroom) {
		String courseName = courseName(detail, item.getTeachingTaskId());
		return new AllocationConflictViolation(
			item.getId(),
			CLASSROOM_CAPACITY,
			"教室容量不足：课程《" + courseName + "》涉及 " + detail.totalStudents() + " 名学生，教室 "
				+ classroomName(classroom) + " 容量为 " + classroom.getCapacity() + "，时间段ID " + item.getTimeSlotId(),
			detail.task().getPrimaryTeacherId(), null, classroom.getId(), item.getTimeSlotId(),
			item.getTeachingTaskId(), courseName, classroom.getCapacity(), detail.totalStudents()
		);
	}

	private AllocationConflictViolation classroomTypeViolation(
		AllocationItem item,
		TeachingTaskDetail detail,
		Classroom classroom,
		String requiredType,
		String classroomType
	) {
		String courseName = courseName(detail, item.getTeachingTaskId());
		return new AllocationConflictViolation(
			item.getId(),
			CLASSROOM_TYPE,
			"教室类型不匹配：课程《" + courseName + "》要求 " + requiredType + "，实际教室 "
				+ classroomName(classroom) + " 类型为 " + classroomType + "，时间段ID " + item.getTimeSlotId(),
			detail.task().getPrimaryTeacherId(), null, classroom.getId(), item.getTimeSlotId(),
			item.getTeachingTaskId(), courseName, null, null
		);
	}

	private String courseName(TeachingTaskDetail detail, Long taskId) {
		if (detail != null && detail.task().getCourse() != null && detail.task().getCourse().getName() != null) {
			return detail.task().getCourse().getName();
		}
		return "教学任务" + taskId;
	}

	private String classroomName(Classroom classroom) {
		return classroom.getName() != null ? classroom.getName() : "教室" + classroom.getId();
	}

	private String normalize(String value) {
		if (value == null || value.isBlank()) {
			return null;
		}
		return value.trim();
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
