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
		SELECT COUNT(*) FROM teacher
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND (name LIKE CONCAT('%', #{keyword}, '%') OR employee_no LIKE CONCAT('%', #{keyword}, '%'))
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		</script>
		""")
	long countAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		<script>
		SELECT id, employee_no, password, role, name, department, title, status, created_at, updated_at
		FROM teacher
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND (name LIKE CONCAT('%', #{keyword}, '%') OR employee_no LIKE CONCAT('%', #{keyword}, '%'))
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		LIMIT #{limit} OFFSET #{offset}
		</script>
		""")
	List<Teacher> findAllPaged(@Param("keyword") String keyword, @Param("status") String status,
							   @Param("limit") int limit, @Param("offset") int offset);

	@Select("""
		<script>
		SELECT id, employee_no, password, role, name, department, title, status, created_at, updated_at
		FROM teacher
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND (name LIKE CONCAT('%', #{keyword}, '%') OR employee_no LIKE CONCAT('%', #{keyword}, '%'))
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<Teacher> findAll(@Param("keyword") String keyword, @Param("status") String status);

	@Select("""
		SELECT id, employee_no, password, role, name, department, title, status, created_at, updated_at
		FROM teacher
		WHERE id = #{id}
		""")
	Teacher findById(Long id);

	@Select("""
		SELECT id, employee_no, password, role, name, department, title, status, created_at, updated_at
		FROM teacher
		WHERE employee_no = #{employeeNo}
		""")
	Teacher findByEmployeeNo(@Param("employeeNo") String employeeNo);

	@Insert("""
		INSERT INTO teacher (employee_no, password, role, name, department, title, status)
		VALUES (#{employeeNo}, #{password}, #{role}, #{name}, #{department}, #{title}, #{status})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(Teacher teacher);

	@Update("""
		UPDATE teacher
		SET employee_no = #{employeeNo},
		    password = #{password},
		    role = #{role},
		    name = #{name},
		    department = #{department},
		    title = #{title},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(Teacher teacher);

	@Update("""
		UPDATE teacher
		SET status = #{status}
		WHERE id = #{id}
		""")
	int deactivate(@Param("id") Long id, @Param("status") String status);
}
