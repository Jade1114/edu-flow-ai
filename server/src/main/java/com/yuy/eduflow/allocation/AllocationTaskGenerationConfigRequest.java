package com.yuy.eduflow.allocation;

import java.math.BigDecimal;

public record AllocationTaskGenerationConfigRequest(
	String allowedWeeks,
	String allowedWeekdays,
	String allowedPeriods,
	Integer schemeCount,
	BigDecimal teacherProfilePenaltyScale,
	BigDecimal distributionPenaltyScale,
	BigDecimal classroomStickinessWeight,
	BigDecimal compactBonusWeight,
	BigDecimal weekdayLoadPenalty,
	BigDecimal roomDayLoadPenalty,
	BigDecimal roomWeekLoadPenalty,
	BigDecimal taskDayLoadPenalty,
	BigDecimal earlyPeriodPenalty,
	BigDecimal latePeriodPenalty,
	BigDecimal randomJitter,
	BigDecimal classroomStickinessBonus,
	BigDecimal weekendPenalty,
	String llmPrompt,
	String llmResultJson
) {
}
