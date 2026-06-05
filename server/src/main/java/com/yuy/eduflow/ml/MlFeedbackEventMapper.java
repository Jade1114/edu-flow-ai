package com.yuy.eduflow.ml;

import java.util.List;
import java.util.Map;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface MlFeedbackEventMapper {

	@Insert("""
		INSERT INTO ml_feedback_event (
		    event_type, task_id, scheme_id, item_id, teaching_task_id,
		    actor_type, actor_id, reason_code, reason_text,
		    before_snapshot_json, after_snapshot_json, context_snapshot_json
		) VALUES (
		    #{eventType}, #{taskId}, #{schemeId}, #{itemId}, #{teachingTaskId},
		    #{actorType}, #{actorId}, #{reasonCode}, #{reasonText},
		    #{beforeSnapshotJson}, #{afterSnapshotJson}, #{contextSnapshotJson}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(MlFeedbackEvent event);

	@Select("""
		<script>
		SELECT COUNT(*)
		FROM ml_feedback_event
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND task_id = #{taskId}
		</if>
		</script>
		""")
	long countAll(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT event_type AS eventType,
		       COUNT(*) AS eventCount
		FROM ml_feedback_event
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND task_id = #{taskId}
		</if>
		GROUP BY event_type
		ORDER BY eventCount DESC, event_type
		</script>
		""")
	List<Map<String, Object>> summarizeByEventType(@Param("taskId") Long taskId);

	@Select("""
		<script>
		SELECT id, event_type AS eventType, task_id AS taskId, scheme_id AS schemeId,
		       item_id AS itemId, teaching_task_id AS teachingTaskId,
		       actor_type AS actorType, reason_code AS reasonCode, reason_text AS reasonText,
		       created_at AS createdAt
		FROM ml_feedback_event
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND task_id = #{taskId}
		</if>
		ORDER BY id DESC
		LIMIT #{limit}
		</script>
		""")
	List<Map<String, Object>> findRecent(@Param("taskId") Long taskId, @Param("limit") int limit);

	@Select("""
		SELECT id, event_type AS eventType, task_id AS taskId, scheme_id AS schemeId,
		       item_id AS itemId, teaching_task_id AS teachingTaskId,
		       actor_type AS actorType, actor_id AS actorId,
		       reason_code AS reasonCode, reason_text AS reasonText,
		       before_snapshot_json AS beforeSnapshotJson,
		       after_snapshot_json AS afterSnapshotJson,
		       context_snapshot_json AS contextSnapshotJson,
		       created_at AS createdAt
		FROM ml_feedback_event
		ORDER BY id DESC
		LIMIT #{limit}
		""")
	List<MlFeedbackEvent> findForProfileAggregation(@Param("limit") int limit);
}
