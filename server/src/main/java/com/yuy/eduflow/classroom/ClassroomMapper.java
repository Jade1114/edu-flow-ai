package com.yuy.eduflow.classroom;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ClassroomMapper {

	@Select("""
		<script>
		SELECT id, name, building, capacity, classroom_type, status, created_at, updated_at
		FROM classroom
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
	List<Classroom> findAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		SELECT id, name, building, capacity, classroom_type, status, created_at, updated_at
		FROM classroom
		WHERE id = #{id}
		""")
	Classroom findById(Long id);

	@Insert("""
		INSERT INTO classroom (name, building, capacity, classroom_type, status)
		VALUES (#{name}, #{building}, #{capacity}, #{classroomType}, #{status})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(Classroom classroom);

	@Update("""
		UPDATE classroom
		SET name = #{name},
		    building = #{building},
		    capacity = #{capacity},
		    classroom_type = #{classroomType},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(Classroom classroom);

	@Update("""
		UPDATE classroom
		SET status = 'INACTIVE'
		WHERE id = #{id}
		""")
	int deactivate(Long id);
}
