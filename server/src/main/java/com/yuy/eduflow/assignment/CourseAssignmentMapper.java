package com.yuy.eduflow.assignment;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface CourseAssignmentMapper {

	@Select("""
		<script>
		SELECT ca.id, ca.source_scheme_id, ca.course_id, ca.class_group_id, ca.teacher_id,
		       ca.classroom_id, ca.time_slot_id, ca.status, ca.created_at, ca.updated_at
		FROM course_assignment ca
		LEFT JOIN time_slot ts ON ca.time_slot_id = ts.id
		WHERE 1 = 1
		<if test='teacherId != null'>
		  AND ca.teacher_id = #{teacherId}
		</if>
		<if test='classGroupId != null'>
		  AND ca.class_group_id = #{classGroupId}
		</if>
		<if test='courseId != null'>
		  AND ca.course_id = #{courseId}
		</if>
		<if test='status != null and status != ""'>
		  AND ca.status = #{status}
		</if>
		<if test='weekNumber != null'>
		  AND ts.week_number = #{weekNumber}
		</if>
		ORDER BY ca.id DESC
		</script>
		""")
	List<CourseAssignment> findAll(
		@Param("teacherId") Long teacherId,
		@Param("classGroupId") Long classGroupId,
		@Param("courseId") Long courseId,
		@Param("status") String status,
		@Param("weekNumber") Integer weekNumber
	);

	@Select("""
		SELECT id, source_scheme_id, course_id, class_group_id, teacher_id,
		       classroom_id, time_slot_id, status, created_at, updated_at
		FROM course_assignment
		WHERE id = #{id}
		""")
	CourseAssignment findById(Long id);

	@Insert("""
		INSERT INTO course_assignment (
		    source_scheme_id, course_id, class_group_id, teacher_id,
		    classroom_id, time_slot_id, status
		)
		VALUES (
		    #{sourceSchemeId}, #{courseId}, #{classGroupId}, #{teacherId},
		    #{classroomId}, #{timeSlotId}, #{status}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(CourseAssignment assignment);

	@Update("""
		UPDATE course_assignment
		SET source_scheme_id = #{sourceSchemeId},
		    course_id = #{courseId},
		    class_group_id = #{classGroupId},
		    teacher_id = #{teacherId},
		    classroom_id = #{classroomId},
		    time_slot_id = #{timeSlotId},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(CourseAssignment assignment);

	@Update("""
		UPDATE course_assignment
		SET status = 'CANCELLED'
		WHERE id = #{id}
		""")
	int cancel(Long id);
}
