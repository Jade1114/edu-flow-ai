package com.yuy.eduflow.allocation;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationItemAdjustmentLog {
	private Long id;
	private Long schemeId;
	private Long itemId;
	private Long teachingTaskId;
	private Long fromTimeSlotId;
	private Long toTimeSlotId;
	private Long fromClassroomId;
	private Long toClassroomId;
	private String reason;
	private String createdBy;
	private LocalDateTime createdAt;
}
