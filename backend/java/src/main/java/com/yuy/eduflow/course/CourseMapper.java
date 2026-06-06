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
		SELECT COUNT(*) FROM course
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		</script>
		""")
	long countAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		<script>
		SELECT id, name, code, credits, course_type, required_room_type, required_hours, description, status, created_at, updated_at
		FROM course
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		LIMIT #{limit} OFFSET #{offset}
		</script>
		""")
	List<Course> findAllPaged(@Param("keyword") String keyword, @Param("status") String status,
							  @Param("limit") int limit, @Param("offset") int offset);

	@Select("""
		<script>
		SELECT id, name, code, credits, course_type, required_hours, description, status, created_at, updated_at
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
		SELECT id, name, code, credits, course_type, required_room_type, required_hours, description, status, created_at, updated_at
		FROM course
		WHERE id = #{id}
		""")
	Course findById(Long id);

	@Insert("""
		INSERT INTO course (name, code, credits, course_type, required_room_type, required_hours, description, status)
		VALUES (#{name}, #{code}, #{credits}, #{courseType}, #{requiredRoomType}, #{requiredHours}, #{description}, #{status})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(Course course);

	@Update("""
		UPDATE course
		SET name = #{name},
		    code = #{code},
		    credits = #{credits},
		    course_type = #{courseType},
		    required_room_type = #{requiredRoomType},
		    required_hours = #{requiredHours},
		    description = #{description},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(Course course);

	@Update("""
		UPDATE course
		SET status = #{status}
		WHERE id = #{id}
		""")
	int deactivate(@Param("id") Long id, @Param("status") String status);
}
