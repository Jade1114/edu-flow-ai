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
		SELECT ca.id,
		       ca.course_id,
		       c.name AS course_name,
		       ca.class_group_id,
		       cg.name AS class_group_name,
		       ca.teacher_id,
		       t.name AS teacher_name,
		       ca.classroom_id,
		       cr.name AS classroom_name,
		       ca.time_slot_id,
		       ts.label AS time_slot_label,
		       ts.week_number,
		       ts.day_of_week,
		       ts.period_index,
		       ca.source_scheme_id,
		       ca.status
		FROM course_assignment ca
		JOIN course c ON ca.course_id = c.id
		JOIN class_group cg ON ca.class_group_id = cg.id
		JOIN teacher t ON ca.teacher_id = t.id
		JOIN classroom cr ON ca.classroom_id = cr.id
		JOIN time_slot ts ON ca.time_slot_id = ts.id
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
		<if test='weekNumber != null'>
		  AND ts.week_number = #{weekNumber}
		</if>
		<if test='dayOfWeek != null'>
		  AND ts.day_of_week = #{dayOfWeek}
		</if>
		<if test='status != null and status != ""'>
		  AND ca.status = #{status}
		</if>
		ORDER BY ts.week_number ASC, ts.day_of_week ASC, ts.period_index ASC, ca.id ASC
		</script>
		""")
	List<CourseAssignmentView> findViews(
		@Param("teacherId") Long teacherId,
		@Param("classGroupId") Long classGroupId,
		@Param("courseId") Long courseId,
		@Param("weekNumber") Integer weekNumber,
		@Param("dayOfWeek") Integer dayOfWeek,
		@Param("status") String status
	);

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

	@Update("""
		UPDATE course_assignment
		SET time_slot_id = #{timeSlotId},
		    classroom_id = #{classroomId}
		WHERE id = #{id}
		""")
	int updateSchedule(
		@Param("id") Long id,
		@Param("timeSlotId") Long timeSlotId,
		@Param("classroomId") Long classroomId
	);

	@Select("""
		SELECT COUNT(*)
		FROM course_assignment
		WHERE status = 'ACTIVE'
		  AND id != #{excludedAssignmentId}
		  AND teacher_id = #{teacherId}
		  AND time_slot_id = #{timeSlotId}
		""")
	int countActiveTeacherTimeConflict(
		@Param("excludedAssignmentId") Long excludedAssignmentId,
		@Param("teacherId") Long teacherId,
		@Param("timeSlotId") Long timeSlotId
	);

	@Select("""
		SELECT COUNT(*)
		FROM course_assignment
		WHERE status = 'ACTIVE'
		  AND id != #{excludedAssignmentId}
		  AND class_group_id = #{classGroupId}
		  AND time_slot_id = #{timeSlotId}
		""")
	int countActiveClassGroupTimeConflict(
		@Param("excludedAssignmentId") Long excludedAssignmentId,
		@Param("classGroupId") Long classGroupId,
		@Param("timeSlotId") Long timeSlotId
	);

	@Select("""
		SELECT COUNT(*)
		FROM course_assignment
		WHERE status = 'ACTIVE'
		  AND id != #{excludedAssignmentId}
		  AND classroom_id = #{classroomId}
		  AND time_slot_id = #{timeSlotId}
		""")
	int countActiveClassroomTimeConflict(
		@Param("excludedAssignmentId") Long excludedAssignmentId,
		@Param("classroomId") Long classroomId,
		@Param("timeSlotId") Long timeSlotId
	);
}
