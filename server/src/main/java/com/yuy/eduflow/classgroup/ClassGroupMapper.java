package com.yuy.eduflow.classgroup;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ClassGroupMapper {

	@Select("""
		<script>
		SELECT COUNT(*) FROM class_group
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		</script>
		""")
	long countAll(@Param("keyword") String keyword);

	@Select("""
		<script>
		SELECT id, name, major, grade, student_count, description, created_at, updated_at
		FROM class_group
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		ORDER BY id DESC
		LIMIT #{limit} OFFSET #{offset}
		</script>
		""")
	List<ClassGroup> findAllPaged(@Param("keyword") String keyword,
								  @Param("limit") int limit, @Param("offset") int offset);

	@Select("""
		<script>
		SELECT id, name, major, grade, student_count, description, created_at, updated_at
		FROM class_group
		WHERE 1 = 1
		<if test='keyword != null and keyword != ""'>
		  AND name LIKE CONCAT('%', #{keyword}, '%')
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<ClassGroup> findAll(@Param("keyword") String keyword);

	@Select("""
		SELECT id, name, major, grade, student_count, description, created_at, updated_at
		FROM class_group
		WHERE id = #{id}
		""")
	ClassGroup findById(Long id);

	@Insert("""
		INSERT INTO class_group (name, major, grade, student_count, description)
		VALUES (#{name}, #{major}, #{grade}, #{studentCount}, #{description})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(ClassGroup classGroup);

	@Update("""
		UPDATE class_group
		SET name = #{name},
		    major = #{major},
		    grade = #{grade},
		    student_count = #{studentCount},
		    description = #{description}
		WHERE id = #{id}
		""")
	int update(ClassGroup classGroup);

	@Delete("""
		DELETE FROM class_group
		WHERE id = #{id}
		""")
	int delete(Long id);
}
