package com.yuy.eduflow.allocation;

import com.yuy.eduflow.enums.SchemeStatus;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationScheme {
	private Long id;
	private Long taskId;
	private String schemeName;
	private String summary;
	private Integer score;
	private Double schemeScore;
	private String evaluationSummary;
	private String policy;
	private String policyParams;
	private String modelVersion;
	private String satisfiedSummary;
	private String conflictSummary;
	private Boolean valid;
    private SchemeStatus status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
