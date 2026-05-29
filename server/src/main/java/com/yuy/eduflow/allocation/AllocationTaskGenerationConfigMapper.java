package com.yuy.eduflow.allocation;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AllocationTaskGenerationConfigMapper {

	@Select("""
		SELECT *
		FROM allocation_task_generation_config
		WHERE task_id = #{taskId}
		""")
	AllocationTaskGenerationConfig findByTaskId(Long taskId);

	@Insert("""
		INSERT INTO allocation_task_generation_config (
			task_id, allowed_weeks, allowed_weekdays, allowed_periods, scheme_count,
			teacher_profile_penalty_scale, distribution_penalty_scale, classroom_stickiness_weight, compact_bonus_weight,
			weekday_load_penalty, room_day_load_penalty, room_week_load_penalty, task_day_load_penalty,
			early_period_penalty, late_period_penalty, random_jitter, classroom_stickiness_bonus, weekend_penalty,
			llm_prompt, llm_result_json, llm_overrides
		) VALUES (
			#{taskId}, #{allowedWeeks}, #{allowedWeekdays}, #{allowedPeriods}, #{schemeCount},
			#{teacherProfilePenaltyScale}, #{distributionPenaltyScale}, #{classroomStickinessWeight}, #{compactBonusWeight},
			#{weekdayLoadPenalty}, #{roomDayLoadPenalty}, #{roomWeekLoadPenalty}, #{taskDayLoadPenalty},
			#{earlyPeriodPenalty}, #{latePeriodPenalty}, #{randomJitter}, #{classroomStickinessBonus}, #{weekendPenalty},
			#{llmPrompt}, #{llmResultJson}, #{llmOverrides}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationTaskGenerationConfig config);

	@Update("""
		UPDATE allocation_task_generation_config
		SET allowed_weeks = #{allowedWeeks},
		    allowed_weekdays = #{allowedWeekdays},
		    allowed_periods = #{allowedPeriods},
		    scheme_count = #{schemeCount},
		    teacher_profile_penalty_scale = #{teacherProfilePenaltyScale},
		    distribution_penalty_scale = #{distributionPenaltyScale},
		    classroom_stickiness_weight = #{classroomStickinessWeight},
		    compact_bonus_weight = #{compactBonusWeight},
		    weekday_load_penalty = #{weekdayLoadPenalty},
		    room_day_load_penalty = #{roomDayLoadPenalty},
		    room_week_load_penalty = #{roomWeekLoadPenalty},
		    task_day_load_penalty = #{taskDayLoadPenalty},
		    early_period_penalty = #{earlyPeriodPenalty},
		    late_period_penalty = #{latePeriodPenalty},
		    random_jitter = #{randomJitter},
		    classroom_stickiness_bonus = #{classroomStickinessBonus},
		    weekend_penalty = #{weekendPenalty},
		    llm_prompt = #{llmPrompt},
		    llm_result_json = #{llmResultJson},
		    llm_overrides = #{llmOverrides}
		WHERE task_id = #{taskId}
		""")
	int updateByTaskId(AllocationTaskGenerationConfig config);

	@Delete("""
		DELETE FROM allocation_task_generation_config
		WHERE task_id = #{taskId}
		""")
	int deleteByTaskId(Long taskId);
}
