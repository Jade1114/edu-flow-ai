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
		       resolved, created_at
		FROM conflict_check_result
		WHERE id = #{id}
		""")
	ConflictCheckResult findById(Long id);

	@Insert("""
		INSERT INTO conflict_check_result (
		    biz_type, biz_id, conflict_type, message, related_teacher_id,
		    related_class_group_id, related_classroom_id, related_time_slot_id,
		    resolved
		)
		VALUES (
		    #{bizType}, #{bizId}, #{conflictType}, #{message}, #{relatedTeacherId},
		    #{relatedClassGroupId}, #{relatedClassroomId}, #{relatedTimeSlotId},
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
