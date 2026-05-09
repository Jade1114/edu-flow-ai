package com.yuy.eduflow.teacher;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TeacherMapper {

	@Select("""
		<script>
		SELECT id, name, department, title, max_weekly_hours, status, created_at, updated_at
		FROM teacher
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
	List<Teacher> findAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		SELECT id, name, department, title, max_weekly_hours, status, created_at, updated_at
		FROM teacher
		WHERE id = #{id}
		""")
	Teacher findById(Long id);

	@Insert("""
		INSERT INTO teacher (name, department, title, max_weekly_hours, status)
		VALUES (#{name}, #{department}, #{title}, #{maxWeeklyHours}, #{status})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(Teacher teacher);

	@Update("""
		UPDATE teacher
		SET name = #{name},
		    department = #{department},
		    title = #{title},
		    max_weekly_hours = #{maxWeeklyHours},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(Teacher teacher);

	@Update("""
		UPDATE teacher
		SET status = 'INACTIVE'
		WHERE id = #{id}
		""")
	int deactivate(Long id);
}
