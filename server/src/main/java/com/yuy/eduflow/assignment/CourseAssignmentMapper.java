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

	List<CourseAssignmentView> findViews(
		@Param("teacherId") Long teacherId,
		@Param("classGroupId") Long classGroupId,
		@Param("courseId") Long courseId,
		@Param("weekNumber") Integer weekNumber,
		@Param("dayOfWeek") Integer dayOfWeek,
		@Param("status") String status
	);

	List<CourseAssignment> findAll(
		@Param("teacherId") Long teacherId,
		@Param("classGroupId") Long classGroupId,
		@Param("courseId") Long courseId,
		@Param("status") String status,
		@Param("weekNumber") Integer weekNumber
	);

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
