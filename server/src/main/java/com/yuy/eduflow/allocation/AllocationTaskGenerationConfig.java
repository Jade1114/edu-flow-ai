package com.yuy.eduflow.allocation;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationTaskGenerationConfig {
	private Long id;
	private Long taskId;
	private String allowedWeeks;
	private String allowedWeekdays;
	private String allowedPeriods;
	private Integer schemeCount;
	private BigDecimal teacherProfilePenaltyScale;
	private BigDecimal distributionPenaltyScale;
	private BigDecimal classroomStickinessWeight;
	private BigDecimal compactBonusWeight;
	private BigDecimal weekdayLoadPenalty;
	private BigDecimal roomDayLoadPenalty;
	private BigDecimal roomWeekLoadPenalty;
	private BigDecimal taskDayLoadPenalty;
	private BigDecimal earlyPeriodPenalty;
	private BigDecimal latePeriodPenalty;
	private BigDecimal randomJitter;
	private BigDecimal classroomStickinessBonus;
	private BigDecimal weekendPenalty;
	private String llmPrompt;
	private String llmResultJson;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
