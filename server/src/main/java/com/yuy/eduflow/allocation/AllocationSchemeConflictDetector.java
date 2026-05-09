package com.yuy.eduflow.allocation;

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

	public List<AllocationConflictViolation> detect(List<AllocationItem> items) {
		if (items == null || items.isEmpty()) {
			return List.of();
		}
		List<AllocationConflictViolation> violations = new ArrayList<>();
		detectConflicts(items, this::teacherKey, this::teacherViolation, violations);
		detectConflicts(items, this::classGroupKey, this::classGroupViolation, violations);
		detectConflicts(items, this::classroomKey, this::classroomViolation, violations);
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
		return "发现 " + violations.size() + " 条冲突记录：" + String.join("，", parts);
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
			if (key.resourceId() == null || key.timeSlotId() == null) {
				continue;
			}
			groupedItems.computeIfAbsent(key, ignored -> new ArrayList<>()).add(item);
		}
		groupedItems.values().stream()
			.filter(group -> group.size() > 1)
			.forEach(group -> group.forEach(item -> violations.add(violationFactory.create(item, group))));
	}

	private ConflictKey teacherKey(AllocationItem item) {
		return new ConflictKey(item.getTeacherId(), item.getTimeSlotId());
	}

	private ConflictKey classGroupKey(AllocationItem item) {
		return new ConflictKey(item.getClassGroupId(), item.getTimeSlotId());
	}

	private ConflictKey classroomKey(AllocationItem item) {
		return new ConflictKey(item.getClassroomId(), item.getTimeSlotId());
	}

	private AllocationConflictViolation teacherViolation(AllocationItem item, List<AllocationItem> group) {
		return new AllocationConflictViolation(
			item.getId(),
			TEACHER_TIME,
			"教师时间冲突：教师ID " + item.getTeacherId() + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			item.getTeacherId(),
			null,
			null,
			item.getTimeSlotId()
		);
	}

	private AllocationConflictViolation classGroupViolation(AllocationItem item, List<AllocationItem> group) {
		return new AllocationConflictViolation(
			item.getId(),
			CLASS_GROUP_TIME,
			"班级时间冲突：班级ID " + item.getClassGroupId() + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复安排，涉及明细ID：" + itemIds(group),
			null,
			item.getClassGroupId(),
			null,
			item.getTimeSlotId()
		);
	}

	private AllocationConflictViolation classroomViolation(AllocationItem item, List<AllocationItem> group) {
		return new AllocationConflictViolation(
			item.getId(),
			CLASSROOM_TIME,
			"教室时间冲突：教室ID " + item.getClassroomId() + " 在时间段ID " + item.getTimeSlotId()
				+ " 被重复占用，涉及明细ID：" + itemIds(group),
			null,
			null,
			item.getClassroomId(),
			item.getTimeSlotId()
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

	@FunctionalInterface
	private interface ConflictViolationFactory {
		AllocationConflictViolation create(AllocationItem item, List<AllocationItem> group);
	}
}
