package com.yuy.eduflow.adjustment;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AdjustmentRequest {
	private Long id;
	private Long assignmentId;
	private Long teacherId;
	private String reason;
	private String preferredTimeText;
	private Long preferredTimeSlotId;
	private Long preferredClassroomId;
	private String aiSuggestion;
	private String status;
	private String reviewNote;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
