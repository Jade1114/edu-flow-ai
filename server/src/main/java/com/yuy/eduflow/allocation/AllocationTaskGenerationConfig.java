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
	private BigDecimal earlyPeriodPenalty;
	private BigDecimal latePeriodPenalty;
	private BigDecimal weekendPenalty;
	private String llmPrompt;
	private String llmResultJson;
	private String llmOverrides;  // JSON array of LLM constraint overrides
	private BigDecimal modelWeight;           // L3 LightGBM score weight (alpha) in quality_score
	private BigDecimal llmWeight;             // L5 LLM override weight (beta) in quality_score
	private BigDecimal sameDayWeight;         // L2 S1: penalty per same-day duplicate assignment
	private BigDecimal capacityWastePenalty;  // L2 S8: penalty if capacity_ratio < 0.6 (0=disabled)
	private BigDecimal teacherDayLoadPenalty; // L2 S5: penalty per extra teacher session on same day
	private BigDecimal classDayLoadPenalty;   // L2 S6: penalty per extra class session on same day
	private BigDecimal teacherOverloadPenalty;// L2 S7: penalty if teacher weekly hours > max
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
