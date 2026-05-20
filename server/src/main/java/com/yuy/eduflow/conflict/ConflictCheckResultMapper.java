package com.yuy.eduflow.conflict;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ConflictCheckResultMapper {

	@Select("""
		<script>
		SELECT id, biz_type, biz_id, conflict_type, message, related_teacher_id,
		       related_class_group_id, related_classroom_id, related_time_slot_id,
		       teaching_task_id, course_name, expected_hours, actual_hours,
		       resolved, created_at
		FROM conflict_check_result
		WHERE 1 = 1
		<if test='bizType != null and bizType != ""'>
		  AND biz_type = #{bizType}
		</if>
		<if test='bizId != null'>
		  AND biz_id = #{bizId}
		</if>
		<if test='conflictType != null and conflictType != ""'>
		  AND conflict_type = #{conflictType}
		</if>
		<if test='resolved != null'>
		  AND resolved = #{resolved}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<ConflictCheckResult> findAll(
		@Param("bizType") String bizType,
		@Param("bizId") Long bizId,
		@Param("conflictType") String conflictType,
		@Param("resolved") Boolean resolved
	);

	@Select("""
		SELECT id, biz_type, biz_id, conflict_type, message, related_teacher_id,
		       related_class_group_id, related_classroom_id, related_time_slot_id,
		       teaching_task_id, course_name, expected_hours, actual_hours,
		       resolved, created_at
		FROM conflict_check_result
		WHERE id = #{id}
		""")
	ConflictCheckResult findById(Long id);

	@Select("""
		SELECT ccr.id, ccr.biz_type, ccr.biz_id, ccr.conflict_type, ccr.message,
		       ccr.related_teacher_id, ccr.related_class_group_id,
		       ccr.related_classroom_id, ccr.related_time_slot_id,
		       ccr.teaching_task_id, ccr.course_name, ccr.expected_hours, ccr.actual_hours,
		       t.name AS related_teacher_name,
		       cg.name AS related_class_group_name,
		       cr.name AS related_classroom_name,
		       CONCAT('第', ts.week_number, '周 ',
		              CASE ts.day_of_week
		                  WHEN 1 THEN '周一' WHEN 2 THEN '周二' WHEN 3 THEN '周三'
		                  WHEN 4 THEN '周四' WHEN 5 THEN '周五' WHEN 6 THEN '周六'
		                  WHEN 7 THEN '周日'
		              END, ' 第', ts.period_index, '节') AS related_time_slot_label,
		       ccr.resolved, ccr.created_at
		FROM conflict_check_result ccr
		LEFT JOIN allocation_item ai ON ccr.biz_id = ai.id
		LEFT JOIN teacher t ON ccr.related_teacher_id = t.id
		LEFT JOIN class_group cg ON ccr.related_class_group_id = cg.id
		LEFT JOIN classroom cr ON ccr.related_classroom_id = cr.id
		LEFT JOIN time_slot ts ON ccr.related_time_slot_id = ts.id
		WHERE (ai.scheme_id = #{schemeId} OR ccr.biz_id = #{schemeId})
		  AND ccr.biz_type IN ('ALLOCATION_ITEM', 'SCHEME')
		ORDER BY ccr.conflict_type, ccr.id DESC
		""")
	List<ConflictCheckResult> findBySchemeId(@Param("schemeId") Long schemeId);

	@Insert("""
		INSERT INTO conflict_check_result (
		    biz_type, biz_id, conflict_type, message, related_teacher_id,
		    related_class_group_id, related_classroom_id, related_time_slot_id,
		    teaching_task_id, course_name, expected_hours, actual_hours,
		    resolved
		)
		VALUES (
		    #{bizType}, #{bizId}, #{conflictType}, #{message}, #{relatedTeacherId},
		    #{relatedClassGroupId}, #{relatedClassroomId}, #{relatedTimeSlotId},
		    #{teachingTaskId}, #{courseName}, #{expectedHours}, #{actualHours},
		    #{resolved}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(ConflictCheckResult result);

	@Update("""
		UPDATE conflict_check_result
		SET biz_type = #{bizType},
		    biz_id = #{bizId},
		    conflict_type = #{conflictType},
		    message = #{message},
		    related_teacher_id = #{relatedTeacherId},
		    related_class_group_id = #{relatedClassGroupId},
		    related_classroom_id = #{relatedClassroomId},
		    related_time_slot_id = #{relatedTimeSlotId},
		    teaching_task_id = #{teachingTaskId},
		    course_name = #{courseName},
		    expected_hours = #{expectedHours},
		    actual_hours = #{actualHours},
		    resolved = #{resolved}
		WHERE id = #{id}
		""")
	int update(ConflictCheckResult result);

	@Delete("""
		DELETE FROM conflict_check_result
		WHERE id = #{id}
		""")
	int delete(Long id);
}
