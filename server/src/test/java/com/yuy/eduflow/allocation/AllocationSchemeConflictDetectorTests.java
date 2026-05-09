package com.yuy.eduflow.allocation;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class AllocationSchemeConflictDetectorTests {
	private final AllocationSchemeConflictDetector detector = new AllocationSchemeConflictDetector();

	@Test
	void detectsTeacherClassGroupAndClassroomTimeConflictsWithinSameScheme() {
		List<AllocationItem> items = List.of(
			item(101L, 1L, 1L, 1L, 1L),
			item(102L, 2L, 2L, 1L, 1L),
			item(103L, 1L, 3L, 3L, 1L),
			item(104L, 4L, 1L, 4L, 1L)
		);

		List<AllocationConflictViolation> violations = detector.detect(items);

		assertThat(violations).hasSize(6);
		assertThat(violations)
			.extracting(AllocationConflictViolation::conflictType)
			.containsExactly(
				AllocationSchemeConflictDetector.TEACHER_TIME,
				AllocationSchemeConflictDetector.TEACHER_TIME,
				AllocationSchemeConflictDetector.CLASS_GROUP_TIME,
				AllocationSchemeConflictDetector.CLASS_GROUP_TIME,
				AllocationSchemeConflictDetector.CLASSROOM_TIME,
				AllocationSchemeConflictDetector.CLASSROOM_TIME
			);
		assertThat(violations)
			.extracting(AllocationConflictViolation::message)
			.anySatisfy(message -> assertThat(message).contains("教师时间冲突", "涉及明细ID：101, 102"))
			.anySatisfy(message -> assertThat(message).contains("班级时间冲突", "涉及明细ID：101, 103"))
			.anySatisfy(message -> assertThat(message).contains("教室时间冲突", "涉及明细ID：101, 104"));
		assertThat(detector.summarize(violations))
			.isEqualTo("发现 6 条冲突记录：教师时间冲突 2 条，班级时间冲突 2 条，教室时间冲突 2 条");
	}

	@Test
	void returnsNoConflictSummaryForIndependentItems() {
		List<AllocationConflictViolation> violations = detector.detect(List.of(
			item(101L, 1L, 1L, 1L, 1L),
			item(102L, 2L, 2L, 2L, 2L)
		));

		assertThat(violations).isEmpty();
		assertThat(detector.summarize(violations)).isEqualTo("无明显冲突");
	}

	private AllocationItem item(Long id, Long classGroupId, Long classroomId, Long teacherId, Long timeSlotId) {
		AllocationItem item = new AllocationItem();
		item.setId(id);
		item.setClassGroupId(classGroupId);
		item.setClassroomId(classroomId);
		item.setTeacherId(teacherId);
		item.setTimeSlotId(timeSlotId);
		return item;
	}
}
