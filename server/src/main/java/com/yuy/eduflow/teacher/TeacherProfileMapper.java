package com.yuy.eduflow.teacher;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TeacherProfileMapper {

	@Select("""
		SELECT id, teacher_id, skill_text, available_time_text, unavailable_time_text,
		       workload_requirement, special_note, vector_text, vector_indexed,
		       created_at, updated_at
		FROM teacher_profile
		WHERE teacher_id = #{teacherId}
		""")
	TeacherProfile findByTeacherId(Long teacherId);

	@Insert("""
		INSERT INTO teacher_profile (
		    teacher_id, skill_text, available_time_text, unavailable_time_text,
		    workload_requirement, special_note, vector_text, vector_indexed
		)
		VALUES (
		    #{teacherId}, #{skillText}, #{availableTimeText}, #{unavailableTimeText},
		    #{workloadRequirement}, #{specialNote}, #{vectorText}, #{vectorIndexed}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(TeacherProfile profile);

	@Update("""
		UPDATE teacher_profile
		SET skill_text = #{skillText},
		    available_time_text = #{availableTimeText},
		    unavailable_time_text = #{unavailableTimeText},
		    workload_requirement = #{workloadRequirement},
		    special_note = #{specialNote},
		    vector_text = #{vectorText},
		    vector_indexed = #{vectorIndexed}
		WHERE teacher_id = #{teacherId}
		""")
	int updateByTeacherId(TeacherProfile profile);
}
