package com.yuy.eduflow.ml;

import java.util.List;
import java.util.Map;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface MlFeedbackTrainingMapper {

	@Insert("""
		INSERT INTO model_training_log (
			model_version, training_type, scheme_count, item_count, feedback_count,
			adjustment_count, conflict_count, sample_count, positive_count, negative_count,
			train_accuracy, train_auc, eval_accuracy, eval_auc, model_path, sample_path,
			metrics_json, status, error_message, train_started_at, train_finished_at
		) VALUES (
			#{modelVersion}, #{trainingType}, #{schemeCount}, #{itemCount}, #{feedbackCount},
			#{adjustmentCount}, #{conflictCount}, #{sampleCount}, #{positiveCount}, #{negativeCount},
			#{trainAccuracy}, #{trainAuc}, #{evalAccuracy}, #{evalAuc}, #{modelPath}, #{samplePath},
			#{metricsJson}, #{status}, #{errorMessage}, #{trainStartedAt}, #{trainFinishedAt}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insertTrainingLog(MlTrainingLog trainingLog);

	@Update("""
		UPDATE model_training_log
		SET scheme_count = #{schemeCount},
		    item_count = #{itemCount},
		    feedback_count = #{feedbackCount},
		    adjustment_count = #{adjustmentCount},
		    conflict_count = #{conflictCount},
		    sample_count = #{sampleCount},
		    positive_count = #{positiveCount},
		    negative_count = #{negativeCount},
		    train_accuracy = #{trainAccuracy},
		    train_auc = #{trainAuc},
		    eval_accuracy = #{evalAccuracy},
		    eval_auc = #{evalAuc},
		    model_path = #{modelPath},
		    sample_path = #{samplePath},
		    metrics_json = #{metricsJson},
		    status = #{status},
		    error_message = #{errorMessage},
		    train_finished_at = #{trainFinishedAt}
		WHERE id = #{id}
		""")
	int updateTrainingLog(MlTrainingLog trainingLog);

	@Select("""
		<script>
		SELECT s.id, s.task_id, s.scheme_name, s.summary, s.scheme_score,
		       s.evaluation_summary, s.policy, s.policy_params, s.model_version,
		       s.satisfied_summary, s.conflict_summary, s.valid, s.status,
		       s.created_at, s.updated_at
		FROM allocation_scheme s
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND s.task_id = #{taskId}
		</if>
		ORDER BY s.id
		</script>
		""")
	List<Map<String, Object>> findSchemes(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT i.id, i.scheme_id, i.teaching_task_id, i.classroom_id, i.time_slot_id,
		       i.valid, i.conflict_message, i.created_at, i.updated_at,
		       s.task_id, s.status AS scheme_status,
		       tt.total_hours, tt.required_room_type,
		       c.course_type,
		       t.department AS teacher_department, t.title AS teacher_title,
		       t.max_weekly_hours AS teacher_max_weekly_hours,
		       cr.capacity AS room_capacity, cr.classroom_type AS room_type, cr.building AS room_building,
		       ts.week_number, ts.day_of_week, ts.period_index,
		       COUNT(cg.id) AS class_group_count,
		       COALESCE(SUM(cg.student_count), 0) AS total_student_count
		FROM allocation_item i
		JOIN allocation_scheme s ON s.id = i.scheme_id
		JOIN teaching_task tt ON tt.id = i.teaching_task_id
		JOIN course c ON c.id = tt.course_id
		JOIN teacher t ON t.id = tt.primary_teacher_id
		JOIN classroom cr ON cr.id = i.classroom_id
		JOIN time_slot ts ON ts.id = i.time_slot_id
		LEFT JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
		LEFT JOIN class_group cg ON cg.id = ttcg.class_group_id
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND s.task_id = #{taskId}
		</if>
		GROUP BY i.id, i.scheme_id, i.teaching_task_id, i.classroom_id, i.time_slot_id,
		         i.valid, i.conflict_message, i.created_at, i.updated_at,
		         s.task_id, s.status, tt.total_hours, tt.required_room_type,
		         c.course_type, t.department, t.title, t.max_weekly_hours,
		         cr.capacity, cr.classroom_type, cr.building,
		         ts.week_number, ts.day_of_week, ts.period_index
		ORDER BY i.id
		</script>
		""")
	List<Map<String, Object>> findItems(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT f.id, f.scheme_id, f.task_id, f.feedback_type,
		       f.adjustment_count, f.created_by, f.created_at
		FROM allocation_scheme_feedback f
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND f.task_id = #{taskId}
		</if>
		ORDER BY f.id
		</script>
		""")
	List<Map<String, Object>> findFeedback(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT l.id, l.scheme_id, l.item_id, l.teaching_task_id,
		       l.from_time_slot_id, l.to_time_slot_id, l.from_classroom_id, l.to_classroom_id,
		       l.reason, l.created_by, l.created_at,
		       s.task_id
		FROM allocation_item_adjustment_log l
		JOIN allocation_scheme s ON s.id = l.scheme_id
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND s.task_id = #{taskId}
		</if>
		ORDER BY l.id
		</script>
		""")
	List<Map<String, Object>> findAdjustmentLogs(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT c.id, c.biz_type, c.biz_id, c.conflict_type, c.message,
		       c.related_teacher_id, c.related_class_group_id, c.related_classroom_id,
		       c.related_time_slot_id, c.resolved, c.created_at,
		       i.scheme_id, s.task_id
		FROM conflict_check_result c
		LEFT JOIN allocation_item i ON c.biz_type = 'ALLOCATION_ITEM' AND c.biz_id = i.id
		LEFT JOIN allocation_scheme s ON s.id = i.scheme_id
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND s.task_id = #{taskId}
		</if>
		ORDER BY c.id
		</script>
		""")
	List<Map<String, Object>> findConflicts(@Param("taskId") Long taskId);

	@Select("""
		SELECT id,
		       model_version AS modelVersion,
		       training_type AS trainingType,
		       scheme_count AS schemeCount,
		       item_count AS itemCount,
		       feedback_count AS feedbackCount,
		       adjustment_count AS adjustmentCount,
		       conflict_count AS conflictCount,
		       sample_count AS sampleCount,
		       positive_count AS positiveCount,
		       negative_count AS negativeCount,
		       train_accuracy AS trainAccuracy,
		       train_auc AS trainAuc,
		       eval_accuracy AS evalAccuracy,
		       eval_auc AS evalAuc,
		       model_path AS modelPath,
		       sample_path AS samplePath,
		       metrics_json AS metricsJson,
		       status,
		       error_message AS errorMessage,
		       train_started_at AS trainStartedAt,
		       train_finished_at AS trainFinishedAt
		FROM model_training_log
		ORDER BY train_started_at DESC
		LIMIT #{limit}
		""")
	List<Map<String, Object>> findTrainingLogs(@Param("limit") int limit);

	@Select("""
		SELECT id,
		       model_version AS modelVersion,
		       training_type AS trainingType,
		       scheme_count AS schemeCount,
		       item_count AS itemCount,
		       feedback_count AS feedbackCount,
		       adjustment_count AS adjustmentCount,
		       conflict_count AS conflictCount,
		       sample_count AS sampleCount,
		       positive_count AS positiveCount,
		       negative_count AS negativeCount,
		       train_accuracy AS trainAccuracy,
		       train_auc AS trainAuc,
		       eval_accuracy AS evalAccuracy,
		       eval_auc AS evalAuc,
		       model_path AS modelPath,
		       sample_path AS samplePath,
		       metrics_json AS metricsJson,
		       status,
		       error_message AS errorMessage,
		       train_started_at AS trainStartedAt,
		       train_finished_at AS trainFinishedAt
		FROM model_training_log
		WHERE status = 'SUCCEEDED'
		ORDER BY train_started_at DESC
		LIMIT 1
		""")
	Map<String, Object> findLatestTrainingLog();
}
