package com.yuy.eduflow.allocation;

import java.math.BigDecimal;

public record AllocationTaskGenerationConfigRequest(
	String allowedWeeks,
	String allowedWeekdays,
	String allowedPeriods,
	Integer schemeCount,
	BigDecimal teacherProfilePenaltyScale,
	BigDecimal earlyPeriodPenalty,
	BigDecimal latePeriodPenalty,
	BigDecimal weekendPenalty,
	String llmPrompt,
	String llmResultJson,
	String llmOverrides
) {
}
