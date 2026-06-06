package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.enums.ActiveStatus;
import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.teachingtask.TeachingTaskMapper;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AllocationBalancedStressTaskService {

	private static final int DEFAULT_TASK_COUNT = 4000;
	private static final int DEFAULT_TOTAL_HOURS = 2;
	private static final String DEFAULT_ALLOWED_WEEKS = "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18";
	private static final String DEFAULT_ALLOWED_WEEKDAYS = "1,2,3,4,5";
	private static final String DEFAULT_ALLOWED_PERIODS = "1,2,3,4,5";

	private final AllocationTaskMapper allocationTaskMapper;
	private final AllocationTaskGenerationConfigMapper generationConfigMapper;
	private final TeachingTaskMapper teachingTaskMapper;
	private final AllocationStressTaskMapper stressTaskMapper;

	public AllocationBalancedStressTaskService(
		AllocationTaskMapper allocationTaskMapper,
		AllocationTaskGenerationConfigMapper generationConfigMapper,
		TeachingTaskMapper teachingTaskMapper,
		AllocationStressTaskMapper stressTaskMapper
	) {
		this.allocationTaskMapper = allocationTaskMapper;
		this.generationConfigMapper = generationConfigMapper;
		this.teachingTaskMapper = teachingTaskMapper;
		this.stressTaskMapper = stressTaskMapper;
	}

	@Transactional
	public BalancedStressTaskResponse createBalanced4000(BalancedStressTaskRequest request) {
		int taskCount = request != null && request.taskCount() != null ? request.taskCount() : DEFAULT_TASK_COUNT;
		int totalHours = request != null && request.totalHours() != null ? request.totalHours() : DEFAULT_TOTAL_HOURS;
		if (taskCount <= 0 || taskCount > 5000) {
			throw new ValidationException("压测教学任务数必须在 1 到 5000 之间");
		}
		if (totalHours <= 0 || totalHours % 2 != 0) {
			throw new ValidationException("totalHours 必须为正偶数");
		}
		String taskName = request != null && request.name() != null && !request.name().isBlank()
			? request.name().trim()
			: "v3-balanced-stress-4000-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"));
		if (stressTaskMapper.findTaskIdByName(taskName) != null) {
			throw new ValidationException("同名分课任务已存在，请换一个任务名称");
		}

		List<Map<String, Object>> teachers = stressTaskMapper.findActiveTeachers();
		List<Map<String, Object>> classGroups = stressTaskMapper.findClassGroups();
		List<Map<String, Object>> courses = stressTaskMapper.findProfessionalCourses();
		requirePool("active teachers", teachers);
		requirePool("class groups", classGroups);
		requirePool("professional courses", courses);

		AllocationTask task = new AllocationTask();
		task.setName(taskName);
		allocationTaskMapper.insert(task);
		AllocationTaskGenerationConfig config = stressGenerationConfig(task.getId(), resolveGenerationMode(request));
		generationConfigMapper.insert(config);

		List<StressRow> rows = balancedRows(taskCount, totalHours, teachers, classGroups, courses);
		for (int i = 0; i < rows.size(); i++) {
			StressRow row = rows.get(i);
			TeachingTask teachingTask = new TeachingTask();
			teachingTask.setCourseId(row.courseId());
			teachingTask.setPrimaryTeacherId(row.teacherId());
			teachingTask.setTotalHours(row.totalHours());
			teachingTask.setRequiredRoomType(row.requiredRoomType());
			teachingTask.setNotes("v3_balanced_stress generated ordinal=" + (i + 1));
			teachingTask.setStatus(ActiveStatus.ACTIVE);
			teachingTaskMapper.insert(teachingTask);
			teachingTaskMapper.insertClassGroup(teachingTask.getId(), row.classGroupId());
			allocationTaskMapper.insertTeachingTask(task.getId(), teachingTask.getId());
		}

		return new BalancedStressTaskResponse(
			task.getId(),
			generationConfigMapper.findByTaskId(task.getId()),
			distributionSummary(rows, teachers.size(), classGroups.size(), courses.size()),
			rows.size()
		);
	}

	private AllocationTaskGenerationConfig stressGenerationConfig(Long taskId, String generationMode) {
		AllocationTaskGenerationConfig config = new AllocationTaskGenerationConfig();
		config.setTaskId(taskId);
		config.setAllowedWeeks(DEFAULT_ALLOWED_WEEKS);
		config.setAllowedWeekdays(DEFAULT_ALLOWED_WEEKDAYS);
		config.setAllowedPeriods(DEFAULT_ALLOWED_PERIODS);
		config.setSchemeCount(1);
		config.setPlacementTopK(64);
		config.setRawPlanCount(64);
		config.setCpPlanCount(16);
		config.setSolverTimeLimitSeconds(1800);
		config.setGenerationMode(generationMode);
		config.setTeacherProfilePenaltyScale(new BigDecimal("80.0000"));
		config.setEarlyPeriodPenalty(new BigDecimal("0.040000"));
		config.setLatePeriodPenalty(new BigDecimal("0.030000"));
		config.setWeekendPenalty(new BigDecimal("0.050000"));
		config.setModelWeight(new BigDecimal("0.600000"));
		config.setLlmWeight(new BigDecimal("0.400000"));
		config.setSameDayWeight(new BigDecimal("0.050000"));
		config.setCapacityWastePenalty(new BigDecimal("0.000000"));
		config.setTeacherDayLoadPenalty(new BigDecimal("0.000000"));
		config.setClassDayLoadPenalty(new BigDecimal("0.000000"));
		config.setTeacherOverloadPenalty(new BigDecimal("0.000000"));
		return config;
	}

	private String resolveGenerationMode(BalancedStressTaskRequest request) {
		if (request == null || request.mode() == null || request.mode().isBlank()) {
			return "AUTO_QUALITY";
		}
		String mode = request.mode().trim().toUpperCase();
		if ("AUTO_QUALITY".equals(mode) || "AUTO_FULL".equals(mode)) {
			return mode;
		}
		throw new ValidationException("4000 压测模式必须为 AUTO_QUALITY 或 AUTO_FULL");
	}

	private List<StressRow> balancedRows(
		int taskCount,
		int totalHours,
		List<Map<String, Object>> teachers,
		List<Map<String, Object>> classGroups,
		List<Map<String, Object>> courses
	) {
		List<StressRow> rows = new ArrayList<>(taskCount);
		for (int index = 0; index < taskCount; index++) {
			var teacher = teachers.get(index % teachers.size());
			var classGroup = classGroups.get(index % classGroups.size());
			var course = courses.get(index % courses.size());
			rows.add(new StressRow(
				longValue(course.get("id")),
				longValue(teacher.get("id")),
				longValue(classGroup.get("id")),
				totalHours,
				stringValue(course.get("requiredRoomType")) == null
					? "普通教室"
					: stringValue(course.get("requiredRoomType"))
			));
		}
		return rows;
	}

	private Long longValue(Object value) {
		if (value instanceof Number number) {
			return number.longValue();
		}
		return Long.parseLong(String.valueOf(value));
	}

	private String stringValue(Object value) {
		return value instanceof String s && !s.isBlank() ? s : null;
	}

	private Map<String, Object> distributionSummary(
		List<StressRow> rows,
		int teacherPoolSize,
		int classGroupPoolSize,
		int coursePoolSize
	) {
		Map<String, Object> summary = new LinkedHashMap<>();
		summary.put("poolSizes", Map.of(
			"teachers", teacherPoolSize,
			"classGroups", classGroupPoolSize,
			"courses", coursePoolSize
		));
		summary.put("teacher", counterStats(rows.stream().map(StressRow::teacherId).toList()));
		summary.put("classGroup", counterStats(rows.stream().map(StressRow::classGroupId).toList()));
		summary.put("course", counterStats(rows.stream().map(StressRow::courseId).toList()));
		summary.put("roomType", counterStats(rows.stream().map(StressRow::requiredRoomType).toList()));
		return summary;
	}

	private Map<String, Object> counterStats(List<?> values) {
		Map<Object, Integer> counts = new LinkedHashMap<>();
		for (Object value : values) {
			counts.put(value, counts.getOrDefault(value, 0) + 1);
		}
		List<Integer> sortedCounts = counts.values().stream().sorted().toList();
		int min = sortedCounts.isEmpty() ? 0 : sortedCounts.get(0);
		int max = sortedCounts.isEmpty() ? 0 : sortedCounts.get(sortedCounts.size() - 1);
		double avg = sortedCounts.isEmpty()
			? 0.0
			: Math.round(sortedCounts.stream().mapToInt(Integer::intValue).average().orElse(0.0) * 100.0) / 100.0;
		List<Map<String, Object>> top5 = counts.entrySet().stream()
			.sorted(Map.Entry.comparingByValue(Comparator.reverseOrder()))
			.limit(5)
			.map(entry -> Map.<String, Object>of("key", entry.getKey(), "count", entry.getValue()))
			.toList();
		Map<String, Object> stats = new LinkedHashMap<>();
		stats.put("distinct", counts.size());
		stats.put("min", min);
		stats.put("max", max);
		stats.put("avg", avg);
		stats.put("maxMinusMin", max - min);
		stats.put("top5", top5);
		return stats;
	}

	private void requirePool(String name, List<?> rows) {
		if (rows == null || rows.isEmpty()) {
			throw new ValidationException("No " + name + " found in DB; import base data before preparing stress tasks.");
		}
	}

	private record StressRow(
		Long courseId,
		Long teacherId,
		Long classGroupId,
		Integer totalHours,
		String requiredRoomType
	) {}
}
