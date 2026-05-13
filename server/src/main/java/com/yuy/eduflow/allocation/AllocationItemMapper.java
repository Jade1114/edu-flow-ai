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
            SELECT id, scheme_id, teaching_task_id, classroom_id,
        		       time_slot_id, valid, conflict_message, created_at, updated_at
		FROM allocation_item
		WHERE 1 = 1
		<if test='schemeId != null'>
		  AND scheme_id = #{schemeId}
		</if>
            <if test='teachingTaskId != null'>
              AND teaching_task_id = #{teachingTaskId}
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
            @Param("teachingTaskId") Long teachingTaskId,
        		@Param("classroomId") Long classroomId,
		@Param("timeSlotId") Long timeSlotId
	);

	@Select("""
            SELECT id, scheme_id, teaching_task_id, classroom_id,
        		       time_slot_id, valid, conflict_message, created_at, updated_at
		FROM allocation_item
		WHERE id = #{id}
		""")
	AllocationItem findById(Long id);

	@Insert("""
		INSERT INTO allocation_item (
                scheme_id, teaching_task_id, classroom_id,
        		    time_slot_id, valid, conflict_message
		)
		VALUES (
                #{schemeId}, #{teachingTaskId}, #{classroomId},
        		    #{timeSlotId}, #{valid}, #{conflictMessage}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationItem item);

	@Update("""
		UPDATE allocation_item
		SET scheme_id = #{schemeId},
                teaching_task_id = #{teachingTaskId},
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

	@Update("""
		UPDATE allocation_item
		SET valid = #{valid},
		    conflict_message = #{conflictMessage}
		WHERE id = #{id}
		""")
	int updateConflictState(
		@Param("id") Long id,
		@Param("valid") Boolean valid,
		@Param("conflictMessage") String conflictMessage
	);

    @Select("""
            SELECT ai.id, ai.scheme_id, ai.teaching_task_id,
                   c.name AS course_name, pt.name AS teacher_name,
                   (SELECT GROUP_CONCAT(cg.name ORDER BY cg.id SEPARATOR ', ')
                    FROM teaching_task_class_group ttcg
                    JOIN class_group cg ON ttcg.class_group_id = cg.id
                    WHERE ttcg.teaching_task_id = tt.id) AS class_group_name,
                   ai.classroom_id, cr.name AS classroom_name,
                   ai.time_slot_id, ts.label AS time_slot_label,
                   ts.week_number, ts.day_of_week, ts.period_index,
                   ai.valid, ai.conflict_message
            FROM allocation_item ai
            JOIN teaching_task tt ON ai.teaching_task_id = tt.id
            JOIN course c ON tt.course_id = c.id
            JOIN teacher pt ON tt.primary_teacher_id = pt.id
            JOIN classroom cr ON ai.classroom_id = cr.id
            JOIN time_slot ts ON ai.time_slot_id = ts.id
            WHERE ai.scheme_id = #{schemeId}
            ORDER BY ai.id
            """)
    List<AllocationItemView> findViewsBySchemeId(Long schemeId);
}
