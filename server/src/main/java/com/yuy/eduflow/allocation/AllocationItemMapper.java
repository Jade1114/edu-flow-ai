package com.yuy.eduflow.allocation;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AllocationItemMapper {

	@Select("""
		<script>
		SELECT id, scheme_id, course_id, class_group_id, teacher_id, classroom_id,
		       time_slot_id, valid, conflict_message, created_at, updated_at
		FROM allocation_item
		WHERE 1 = 1
		<if test='schemeId != null'>
		  AND scheme_id = #{schemeId}
		</if>
		<if test='teacherId != null'>
		  AND teacher_id = #{teacherId}
		</if>
		<if test='classGroupId != null'>
		  AND class_group_id = #{classGroupId}
		</if>
		<if test='classroomId != null'>
		  AND classroom_id = #{classroomId}
		</if>
		<if test='timeSlotId != null'>
		  AND time_slot_id = #{timeSlotId}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<AllocationItem> findAll(
		@Param("schemeId") Long schemeId,
		@Param("teacherId") Long teacherId,
		@Param("classGroupId") Long classGroupId,
		@Param("classroomId") Long classroomId,
		@Param("timeSlotId") Long timeSlotId
	);

	@Select("""
		SELECT id, scheme_id, course_id, class_group_id, teacher_id, classroom_id,
		       time_slot_id, valid, conflict_message, created_at, updated_at
		FROM allocation_item
		WHERE id = #{id}
		""")
	AllocationItem findById(Long id);

	@Insert("""
		INSERT INTO allocation_item (
		    scheme_id, course_id, class_group_id, teacher_id, classroom_id,
		    time_slot_id, valid, conflict_message
		)
		VALUES (
		    #{schemeId}, #{courseId}, #{classGroupId}, #{teacherId}, #{classroomId},
		    #{timeSlotId}, #{valid}, #{conflictMessage}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationItem item);

	@Update("""
		UPDATE allocation_item
		SET scheme_id = #{schemeId},
		    course_id = #{courseId},
		    class_group_id = #{classGroupId},
		    teacher_id = #{teacherId},
		    classroom_id = #{classroomId},
		    time_slot_id = #{timeSlotId},
		    valid = #{valid},
		    conflict_message = #{conflictMessage}
		WHERE id = #{id}
		""")
	int update(AllocationItem item);

	@Delete("""
		DELETE FROM allocation_item
		WHERE id = #{id}
		""")
	int delete(Long id);
}
