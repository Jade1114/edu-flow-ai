package com.yuy.eduflow.allocation;

import java.math.BigDecimal;

public record AllocationTaskGenerationConfigRequest(
	String allowedWeeks,
	String allowedWeekdays,
	String allowedPeriods,
	Integer schemeCount,
	Integer placementTopK,
	Integer rawPlanCount,
	Integer cpPlanCount,
	Integer solverTimeLimitSeconds,
	String generationMode,
	BigDecimal teacherProfilePenaltyScale,
	BigDecimal earlyPeriodPenalty,
	BigDecimal latePeriodPenalty,
	BigDecimal weekendPenalty,
	String llmPrompt,
	String llmResultJson,
	String llmOverrides,
	BigDecimal modelWeight,
	BigDecimal llmWeight,
	BigDecimal sameDayWeight,
	BigDecimal capacityWastePenalty,
	BigDecimal teacherDayLoadPenalty,
	BigDecimal classDayLoadPenalty,
	BigDecimal teacherOverloadPenalty
) {
}
