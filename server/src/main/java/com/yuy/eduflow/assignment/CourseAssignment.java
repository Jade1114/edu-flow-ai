package com.yuy.eduflow.assignment;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class CourseAssignment {
	private Long id;
	private Long sourceSchemeId;
	private Long courseId;
	private Long classGroupId;
	private Long teacherId;
	private Long classroomId;
	private Long timeSlotId;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
