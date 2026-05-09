package com.yuy.eduflow.allocation;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationTask {
	private Long id;
	private String name;
	private String description;
	private String priorityRule;
	private String status;
	private String createdBy;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
