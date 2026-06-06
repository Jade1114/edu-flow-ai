package com.yuy.eduflow.allocation;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationSchemeFeedback {
	private Long id;
	private Long schemeId;
	private Long taskId;
	private String feedbackType;
	private Integer adjustmentCount;
	private String createdBy;
	private LocalDateTime createdAt;
}
