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
public interface AllocationTaskMapper {

	@Select("""
		<script>
		SELECT id, name, description, start_week, end_week, status, created_by, created_at, updated_at
		FROM allocation_task
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<AllocationTask> findAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		SELECT id, name, description, start_week, end_week, status, created_by, created_at, updated_at
		FROM allocation_task
		WHERE id = #{id}
		""")
	AllocationTask findById(Long id);

	@Insert("""
		INSERT INTO allocation_task (name, description, start_week, end_week, status, created_by)
		VALUES (#{name}, #{description}, #{startWeek}, #{endWeek}, #{status}, #{createdBy})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationTask task);

	@Update("""
		UPDATE allocation_task
		SET name = #{name},
		    description = #{description},
		    start_week = #{startWeek},
		    end_week = #{endWeek},
		    status = #{status},
		    created_by = #{createdBy}
		WHERE id = #{id}
		""")
	int update(AllocationTask task);

	@Update("""
		UPDATE allocation_task
		SET status = #{status}
		WHERE id = #{id}
		""")
	int cancel(@Param("id") Long id, @Param("status") String status);

	@Update("""
		UPDATE allocation_task
		SET status = #{status}
		WHERE id = #{id}
		""")
	int updateStatus(@Param("id") Long id, @Param("status") String status);

	// === 排课任务与教学任务关联 ===
	@Insert("""
		INSERT INTO allocation_task_teaching_task (allocation_task_id, teaching_task_id)
		VALUES (#{allocationTaskId}, #{teachingTaskId})
		""")
	int insertTeachingTask(@Param("allocationTaskId") Long allocationTaskId, @Param("teachingTaskId") Long teachingTaskId);

	@Delete("""
		DELETE FROM allocation_task_teaching_task
		WHERE allocation_task_id = #{allocationTaskId}
		""")
	int deleteTeachingTasks(Long allocationTaskId);

	@Select("""
		SELECT tt.id, tt.course_id, tt.primary_teacher_id, tt.assistant_teacher_id,
		       tt.total_hours, tt.classroom_id, tt.notes, tt.status,
		       tt.created_at, tt.updated_at,
		       c.id AS course_id2, c.name AS course_name,
		       pt.id AS pt_id, pt.name AS primary_teacher_name,
		       at.id AS at_id, at.name AS assistant_teacher_name
		FROM teaching_task tt
		LEFT JOIN course c ON tt.course_id = c.id
		LEFT JOIN teacher pt ON tt.primary_teacher_id = pt.id
		LEFT JOIN teacher at ON tt.assistant_teacher_id = at.id
		JOIN allocation_task_teaching_task att ON tt.id = att.teaching_task_id
		WHERE att.allocation_task_id = #{allocationTaskId}
		ORDER BY tt.id
		""")
	List<AllocationTaskTeachingTaskResult> findTeachingTasks(Long allocationTaskId);
}
