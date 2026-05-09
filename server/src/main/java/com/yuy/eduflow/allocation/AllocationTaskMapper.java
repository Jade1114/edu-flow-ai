package com.yuy.eduflow.allocation;

import java.util.List;
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
		SELECT id, name, description, priority_rule, status, created_by, created_at, updated_at
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
		SELECT id, name, description, priority_rule, status, created_by, created_at, updated_at
		FROM allocation_task
		WHERE id = #{id}
		""")
	AllocationTask findById(Long id);

	@Insert("""
		INSERT INTO allocation_task (name, description, priority_rule, status, created_by)
		VALUES (#{name}, #{description}, #{priorityRule}, #{status}, #{createdBy})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationTask task);

	@Update("""
		UPDATE allocation_task
		SET name = #{name},
		    description = #{description},
		    priority_rule = #{priorityRule},
		    status = #{status},
		    created_by = #{createdBy}
		WHERE id = #{id}
		""")
	int update(AllocationTask task);

	@Update("""
		UPDATE allocation_task
		SET status = 'CANCELLED'
		WHERE id = #{id}
		""")
	int cancel(Long id);

	@Update("""
		UPDATE allocation_task
		SET status = #{status}
		WHERE id = #{id}
		""")
	int updateStatus(@Param("id") Long id, @Param("status") String status);
}
