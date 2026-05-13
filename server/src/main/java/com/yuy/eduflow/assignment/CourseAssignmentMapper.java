package com.yuy.eduflow.assignment;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
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
		SELECT ca.id, ca.source_scheme_id, ca.teaching_task_id,
		       c.id AS course_id, c.name AS course_name,
		       pt.id AS teacher_id, pt.name AS teacher_name,
		       cr.id AS classroom_id, cr.name AS classroom_name,
		       ts.id AS time_slot_id, ts.label AS time_slot_label,
		       ts.week_number, ts.day_of_week, ts.period_index,
		       ca.status,
		       (SELECT GROUP_CONCAT(cg.name ORDER BY cg.id SEPARATOR ', ')
		        FROM teaching_task_class_group ttcg
		        JOIN class_group cg ON ttcg.class_group_id = cg.id
		        WHERE ttcg.teaching_task_id = tt.id) AS class_group_name,
		       (SELECT ttcg.class_group_id FROM teaching_task_class_group ttcg
		        WHERE ttcg.teaching_task_id = tt.id LIMIT 1) AS class_group_id
		FROM course_assignment ca
		JOIN teaching_task tt ON ca.teaching_task_id = tt.id
		JOIN course c ON tt.course_id = c.id
		JOIN teacher pt ON tt.primary_teacher_id = pt.id
		JOIN classroom cr ON ca.classroom_id = cr.id
		JOIN time_slot ts ON ca.time_slot_id = ts.id
		WHERE 1 = 1
		<if test='teacherId != null'>
		  AND tt.primary_teacher_id = #{teacherId}
		</if>
		<if test='classGroupId != null'>
		  AND EXISTS (
		    SELECT 1 FROM teaching_task_class_group ttcg2
		    WHERE ttcg2.teaching_task_id = tt.id AND ttcg2.class_group_id = #{classGroupId}
		  )
		</if>
		<if test='courseId != null'>
		  AND tt.course_id = #{courseId}
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
		SELECT ca.id, ca.source_scheme_id, ca.teaching_task_id,
		       ca.classroom_id, ca.time_slot_id, ca.status, ca.created_at, ca.updated_at
		FROM course_assignment ca
		LEFT JOIN time_slot ts ON ca.time_slot_id = ts.id
		JOIN teaching_task tt ON ca.teaching_task_id = tt.id
		WHERE 1 = 1
		<if test='teacherId != null'>
		  AND tt.primary_teacher_id = #{teacherId}
		</if>
		<if test='classGroupId != null'>
		  AND EXISTS (
		    SELECT 1 FROM teaching_task_class_group ttcg
		    WHERE ttcg.teaching_task_id = tt.id AND ttcg.class_group_id = #{classGroupId}
		  )
		</if>
		<if test='courseId != null'>
		  AND tt.course_id = #{courseId}
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
		SELECT ca.id, ca.source_scheme_id, ca.teaching_task_id,
		       ca.classroom_id, ca.time_slot_id, ca.status, ca.created_at, ca.updated_at,
		       tt.course_id, tt.primary_teacher_id AS teacher_id,
		       (SELECT ttcg.class_group_id FROM teaching_task_class_group ttcg
		        WHERE ttcg.teaching_task_id = tt.id LIMIT 1) AS class_group_id
		FROM course_assignment ca
		JOIN teaching_task tt ON ca.teaching_task_id = tt.id
		WHERE ca.id = #{id}
		""")
	CourseAssignment findById(Long id);

	@Insert("""
		INSERT INTO course_assignment (
		    source_scheme_id, teaching_task_id,
		    classroom_id, time_slot_id, status
		)
		VALUES (
		    #{sourceSchemeId}, #{teachingTaskId},
		    #{classroomId}, #{timeSlotId}, #{status}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(CourseAssignment assignment);

	@Update("""
		UPDATE course_assignment
		SET source_scheme_id = #{sourceSchemeId},
		    teaching_task_id = #{teachingTaskId},
		    classroom_id = #{classroomId},
		    time_slot_id = #{timeSlotId},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(CourseAssignment assignment);

	@Update("""
		UPDATE course_assignment
		SET status = #{status}
		WHERE id = #{id}
		""")
	int cancel(@Param("id") Long id, @Param("status") String status);

	@Delete("""
		DELETE FROM course_assignment
		WHERE source_scheme_id = #{schemeId}
		""")
	int deleteBySourceSchemeId(@Param("schemeId") Long schemeId);

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
		FROM course_assignment ca
		JOIN teaching_task tt ON ca.teaching_task_id = tt.id
		WHERE ca.status = 'ACTIVE'
		  AND ca.id != #{excludedAssignmentId}
		  AND tt.primary_teacher_id = #{teacherId}
		  AND ca.time_slot_id = #{timeSlotId}
		""")
	int countActiveTeacherTimeConflict(
		@Param("excludedAssignmentId") Long excludedAssignmentId,
		@Param("teacherId") Long teacherId,
		@Param("timeSlotId") Long timeSlotId
	);

	@Select("""
		SELECT COUNT(*)
		FROM course_assignment ca
		JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = ca.teaching_task_id
		WHERE ca.status = 'ACTIVE'
		  AND ca.id != #{excludedAssignmentId}
		  AND ttcg.class_group_id = #{classGroupId}
		  AND ca.time_slot_id = #{timeSlotId}
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
