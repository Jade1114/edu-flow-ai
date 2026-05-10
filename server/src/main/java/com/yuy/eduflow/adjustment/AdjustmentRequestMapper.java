package com.yuy.eduflow.adjustment;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AdjustmentRequestMapper {

	@Select("""
		<script>
		SELECT id, assignment_id, teacher_id, reason, preferred_time_text,
		       preferred_time_slot_id, preferred_classroom_id, ai_suggestion,
		       status, review_note, created_at, updated_at
		FROM adjustment_request
		WHERE 1 = 1
		<if test='assignmentId != null'>
		  AND assignment_id = #{assignmentId}
		</if>
		<if test='teacherId != null'>
		  AND teacher_id = #{teacherId}
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<AdjustmentRequest> findAll(
		@Param("assignmentId") Long assignmentId,
		@Param("teacherId") Long teacherId,
		@Param("status") String status
	);

	@Select("""
		SELECT id, assignment_id, teacher_id, reason, preferred_time_text,
		       preferred_time_slot_id, preferred_classroom_id, ai_suggestion,
		       status, review_note, created_at, updated_at
		FROM adjustment_request
		WHERE id = #{id}
		""")
	AdjustmentRequest findById(Long id);

	@Insert("""
		INSERT INTO adjustment_request (
		    assignment_id, teacher_id, reason, preferred_time_text,
		    preferred_time_slot_id, preferred_classroom_id, ai_suggestion,
		    status, review_note
		)
		VALUES (
		    #{assignmentId}, #{teacherId}, #{reason}, #{preferredTimeText},
		    #{preferredTimeSlotId}, #{preferredClassroomId}, #{aiSuggestion},
		    #{status}, #{reviewNote}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AdjustmentRequest request);

	@Update("""
		UPDATE adjustment_request
		SET assignment_id = #{assignmentId},
		    teacher_id = #{teacherId},
		    reason = #{reason},
		    preferred_time_text = #{preferredTimeText},
		    preferred_time_slot_id = #{preferredTimeSlotId},
		    preferred_classroom_id = #{preferredClassroomId},
		    ai_suggestion = #{aiSuggestion},
		    status = #{status},
		    review_note = #{reviewNote}
		WHERE id = #{id}
		""")
	int update(AdjustmentRequest request);

	@Update("""
		UPDATE adjustment_request
		SET status = 'CANCELLED'
		WHERE id = #{id}
		""")
	int cancel(Long id);

	@Update("""
		UPDATE adjustment_request
		SET ai_suggestion = #{aiSuggestion}
		WHERE id = #{id}
		""")
	int updateAiSuggestion(@Param("id") Long id, @Param("aiSuggestion") String aiSuggestion);

	@Update("""
		UPDATE adjustment_request
		SET status = #{status},
		    review_note = #{reviewNote}
		WHERE id = #{id}
		""")
	int updateReviewState(
		@Param("id") Long id,
		@Param("status") String status,
		@Param("reviewNote") String reviewNote
	);
}
