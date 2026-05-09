package com.yuy.eduflow.course;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface CourseMapper {

	@Select("""
		<script>
		SELECT id, name, course_type, required_hours, required_skill, description, status, created_at, updated_at
		FROM course
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
	List<Course> findAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		SELECT id, name, course_type, required_hours, required_skill, description, status, created_at, updated_at
		FROM course
		WHERE id = #{id}
		""")
	Course findById(Long id);

	@Insert("""
		INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
		VALUES (#{name}, #{courseType}, #{requiredHours}, #{requiredSkill}, #{description}, #{status})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(Course course);

	@Update("""
		UPDATE course
		SET name = #{name},
		    course_type = #{courseType},
		    required_hours = #{requiredHours},
		    required_skill = #{requiredSkill},
		    description = #{description},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(Course course);

	@Update("""
		UPDATE course
		SET status = 'INACTIVE'
		WHERE id = #{id}
		""")
	int deactivate(Long id);
}
