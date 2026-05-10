package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class AdjustmentSuggestionConflictDetector {
	private final CourseAssignmentMapper courseAssignmentMapper;

	public AdjustmentSuggestionConflictDetector(CourseAssignmentMapper courseAssignmentMapper) {
		this.courseAssignmentMapper = courseAssignmentMapper;
	}

	public AdjustmentSuggestionCandidate detect(CourseAssignment originalAssignment, AdjustmentSuggestionCandidate candidate) {
		List<String> messages = new ArrayList<>();
		appendConflict(
			messages,
			courseAssignmentMapper.countActiveTeacherTimeConflict(
				originalAssignment.getId(),
				originalAssignment.getTeacherId(),
				candidate.newTimeSlotId()
			),
			"教师在目标时间段已有其他 ACTIVE 课程安排"
		);
		appendConflict(
			messages,
			courseAssignmentMapper.countActiveClassGroupTimeConflict(
				originalAssignment.getId(),
				originalAssignment.getClassGroupId(),
				candidate.newTimeSlotId()
			),
			"班级在目标时间段已有其他 ACTIVE 课程安排"
		);
		appendConflict(
			messages,
			courseAssignmentMapper.countActiveClassroomTimeConflict(
				originalAssignment.getId(),
				candidate.newClassroomId(),
				candidate.newTimeSlotId()
			),
			"教室在目标时间段已有其他 ACTIVE 课程安排"
		);
		if (messages.isEmpty()) {
			return candidate.withConflictState(true, null);
		}
		return candidate.withConflictState(false, String.join("；", messages));
	}

	private void appendConflict(List<String> messages, int count, String message) {
		if (count > 0) {
			messages.add(message + "（" + count + " 条）");
		}
	}
}
