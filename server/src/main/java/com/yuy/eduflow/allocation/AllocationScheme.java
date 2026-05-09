package com.yuy.eduflow.allocation;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationScheme {
	private Long id;
	private Long taskId;
	private String schemeName;
	private String summary;
	private Integer score;
	private String satisfiedSummary;
	private String conflictSummary;
	private Boolean valid;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
