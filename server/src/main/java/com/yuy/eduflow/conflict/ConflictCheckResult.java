package com.yuy.eduflow.conflict;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class ConflictCheckResult {
	private Long id;
	private String bizType;
	private Long bizId;
	private String conflictType;
	private String message;
	private Long relatedTeacherId;
	private Long relatedClassGroupId;
	private Long relatedClassroomId;
	private Long relatedTimeSlotId;
	private Boolean resolved;
	private LocalDateTime createdAt;
}
