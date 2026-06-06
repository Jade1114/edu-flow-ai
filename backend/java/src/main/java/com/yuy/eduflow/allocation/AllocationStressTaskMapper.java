package com.yuy.eduflow.allocation;

import java.util.List;
import java.util.Map;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AllocationStressTaskMapper {

	@Select("""
		SELECT id, name
		FROM teacher
		WHERE status = 'ACTIVE'
		ORDER BY id
		""")
	List<Map<String, Object>> findActiveTeachers();

	@Select("""
		SELECT id, name
		FROM class_group
		ORDER BY id
		""")
	List<Map<String, Object>> findClassGroups();

	@Select("""
		SELECT id, name, code, required_room_type AS requiredRoomType
		FROM course
		WHERE status = 'ACTIVE'
		  AND COALESCE(course_type, '') <> '实践课'
		  AND required_room_type IS NOT NULL
		ORDER BY id
		""")
	List<Map<String, Object>> findProfessionalCourses();

	@Select("""
		SELECT id
		FROM allocation_task
		WHERE name = #{name}
		""")
	Long findTaskIdByName(@Param("name") String name);

}
