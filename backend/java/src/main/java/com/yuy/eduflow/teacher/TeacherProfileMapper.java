package com.yuy.eduflow.teacher;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TeacherProfileMapper {

    @Select("""
        SELECT id, teacher_id,
               availability_matrix_json, profile_note, profile_preference_json,
               created_at, updated_at
        FROM teacher_profile
        WHERE teacher_id = #{teacherId}
        """)
	TeacherProfile findByTeacherId(Long teacherId);

    @Select("""
        SELECT DISTINCT p.id, p.teacher_id,
               p.availability_matrix_json, p.profile_note, p.profile_preference_json,
               p.created_at, p.updated_at
        FROM allocation_task_teaching_task att
        JOIN teaching_task tt ON tt.id = att.teaching_task_id
        JOIN teacher_profile p ON p.teacher_id = tt.primary_teacher_id
        WHERE att.allocation_task_id = #{taskId}
        ORDER BY p.teacher_id
        """)
    List<TeacherProfile> findByAllocationTaskId(Long taskId);

    @Insert("""
        INSERT INTO teacher_profile (
            teacher_id, availability_matrix_json, profile_note, profile_preference_json
        )
        VALUES (
            #{teacherId}, #{availabilityMatrixJson}, #{profileNote}, #{profilePreferenceJson}
        )
        """)
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(TeacherProfile profile);

    @Update("""
        UPDATE teacher_profile
        SET availability_matrix_json = #{availabilityMatrixJson},
            profile_note = #{profileNote},
            profile_preference_json = #{profilePreferenceJson}
        WHERE teacher_id = #{teacherId}
        """)
	int updateByTeacherId(TeacherProfile profile);
}
