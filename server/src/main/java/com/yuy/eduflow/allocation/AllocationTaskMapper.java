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

	List<AllocationTaskTeachingTaskResult> findTeachingTasks(Long allocationTaskId);
}
