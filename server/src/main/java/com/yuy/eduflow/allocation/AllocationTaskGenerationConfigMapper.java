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
			placement_top_k, raw_plan_count, cp_plan_count, solver_time_limit_seconds,
			generation_mode,
			teacher_profile_penalty_scale,
			early_period_penalty, late_period_penalty, weekend_penalty,
			llm_prompt, llm_result_json, llm_overrides,
			model_weight, llm_weight, same_day_weight, capacity_waste_penalty,
			teacher_day_load_penalty, class_day_load_penalty, teacher_overload_penalty
		) VALUES (
			#{taskId}, #{allowedWeeks}, #{allowedWeekdays}, #{allowedPeriods}, #{schemeCount},
			#{placementTopK}, #{rawPlanCount}, #{cpPlanCount}, #{solverTimeLimitSeconds},
			#{generationMode},
			#{teacherProfilePenaltyScale},
			#{earlyPeriodPenalty}, #{latePeriodPenalty}, #{weekendPenalty},
			#{llmPrompt}, #{llmResultJson}, #{llmOverrides},
			#{modelWeight}, #{llmWeight}, #{sameDayWeight}, #{capacityWastePenalty},
			#{teacherDayLoadPenalty}, #{classDayLoadPenalty}, #{teacherOverloadPenalty}
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
		    placement_top_k = #{placementTopK},
		    raw_plan_count = #{rawPlanCount},
		    cp_plan_count = #{cpPlanCount},
		    solver_time_limit_seconds = #{solverTimeLimitSeconds},
		    generation_mode = #{generationMode},
		    teacher_profile_penalty_scale = #{teacherProfilePenaltyScale},
		    early_period_penalty = #{earlyPeriodPenalty},
		    late_period_penalty = #{latePeriodPenalty},
		    weekend_penalty = #{weekendPenalty},
		    llm_prompt = #{llmPrompt},
		    llm_result_json = #{llmResultJson},
		    llm_overrides = #{llmOverrides},
		    model_weight = #{modelWeight},
		    llm_weight = #{llmWeight},
		    same_day_weight = #{sameDayWeight},
		    capacity_waste_penalty = #{capacityWastePenalty},
		    teacher_day_load_penalty = #{teacherDayLoadPenalty},
		    class_day_load_penalty = #{classDayLoadPenalty},
		    teacher_overload_penalty = #{teacherOverloadPenalty}
		WHERE task_id = #{taskId}
		""")
	int updateByTaskId(AllocationTaskGenerationConfig config);

	@Delete("""
		DELETE FROM allocation_task_generation_config
		WHERE task_id = #{taskId}
		""")
	int deleteByTaskId(Long taskId);
}
