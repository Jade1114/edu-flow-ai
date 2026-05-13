package com.yuy.eduflow.allocation;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationItem {
	private Long id;
	private Long schemeId;
	private Long teachingTaskId;
	private Long classroomId;
	private Long timeSlotId;
	private Boolean valid;
	private String conflictMessage;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
