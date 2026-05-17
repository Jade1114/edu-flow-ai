package com.yuy.eduflow.allocation;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AllocationSchemeFeedbackMapper {

	@Select("""
		SELECT id, scheme_id, task_id, feedback_type,
		       adjustment_count, created_by, created_at
		FROM allocation_scheme_feedback
		WHERE scheme_id = #{schemeId}
		ORDER BY id DESC
		""")
	List<AllocationSchemeFeedback> findBySchemeId(Long schemeId);

	@Select("""
		SELECT id, scheme_id, task_id, feedback_type,
		       adjustment_count, created_by, created_at
		FROM allocation_scheme_feedback
		WHERE task_id = #{taskId}
		ORDER BY id DESC
		""")
	List<AllocationSchemeFeedback> findByTaskId(Long taskId);

	@Insert("""
		INSERT INTO allocation_scheme_feedback (
		    scheme_id, task_id, feedback_type,
		    adjustment_count, created_by
		) VALUES (
		    #{schemeId}, #{taskId}, #{feedbackType},
		    #{adjustmentCount}, #{createdBy}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationSchemeFeedback feedback);
}
