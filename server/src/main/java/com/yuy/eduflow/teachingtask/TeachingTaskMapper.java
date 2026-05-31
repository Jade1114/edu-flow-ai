package com.yuy.eduflow.teachingtask;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classroom.Classroom;
import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TeachingTaskMapper {

    List<TeachingTask> findAll(
            @Param("status") String status,
            @Param("courseId") Long courseId,
            @Param("teacherId") Long teacherId);

    long findAllCount(
            @Param("status") String status,
            @Param("courseId") Long courseId,
            @Param("teacherId") Long teacherId);

    List<TeachingTask> findAllPaged(
            @Param("status") String status,
            @Param("courseId") Long courseId,
            @Param("teacherId") Long teacherId,
            @Param("limit") int limit,
            @Param("offset") int offset);

    TeachingTask findById(Long id);

    @Insert("""
            INSERT INTO teaching_task (
                course_id, primary_teacher_id, assistant_teacher_id, classroom_id,
                total_hours, required_room_type, notes, status
            )
            VALUES (
                #{courseId}, #{primaryTeacherId}, #{assistantTeacherId}, #{classroomId},
                #{totalHours}, #{requiredRoomType}, #{notes}, #{status}
            )
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(TeachingTask task);

    @Update("""
            UPDATE teaching_task
            SET course_id = #{courseId},
                primary_teacher_id = #{primaryTeacherId},
                assistant_teacher_id = #{assistantTeacherId},
                classroom_id = #{classroomId},
                total_hours = #{totalHours},
                required_room_type = #{requiredRoomType},
                notes = #{notes},
                status = #{status}
            WHERE id = #{id}
            """)
    int update(TeachingTask task);

    @Delete("""
            DELETE FROM teaching_task
            WHERE id = #{id}
            """)
    int delete(Long id);

    // === 班级关联 ===
    @Insert("""
            INSERT INTO teaching_task_class_group (teaching_task_id, class_group_id)
            VALUES (#{teachingTaskId}, #{classGroupId})
            """)
    int insertClassGroup(@Param("teachingTaskId") Long teachingTaskId, @Param("classGroupId") Long classGroupId);

    @Delete("""
            DELETE FROM teaching_task_class_group
            WHERE teaching_task_id = #{teachingTaskId}
            """)
    int deleteClassGroups(Long teachingTaskId);

    @Select("""
            SELECT cg.id, cg.name, cg.major, cg.department, cg.grade, cg.student_count, cg.description
            FROM class_group cg
            JOIN teaching_task_class_group ttcg ON cg.id = ttcg.class_group_id
            WHERE ttcg.teaching_task_id = #{teachingTaskId}
            ORDER BY cg.id
            """)
    List<ClassGroup> findClassGroups(Long teachingTaskId);

    // === 候选教室关联 ===
    @Insert("""
            INSERT INTO teaching_task_classroom (teaching_task_id, classroom_id)
            VALUES (#{teachingTaskId}, #{classroomId})
            """)
    int insertClassroom(@Param("teachingTaskId") Long teachingTaskId, @Param("classroomId") Long classroomId);

    @Delete("""
            DELETE FROM teaching_task_classroom
            WHERE teaching_task_id = #{teachingTaskId}
            """)
    int deleteClassrooms(Long teachingTaskId);

    @Select("""
            SELECT cr.id, cr.name, cr.building, cr.capacity, cr.classroom_type, cr.status
            FROM classroom cr
            JOIN teaching_task_classroom ttc ON cr.id = ttc.classroom_id
            WHERE ttc.teaching_task_id = #{teachingTaskId}
            ORDER BY cr.id
            """)
    List<Classroom> findClassrooms(Long teachingTaskId);

    // === 获取教学任务完整详情 ===
    TeachingTask findWithDetails(Long id);
}
