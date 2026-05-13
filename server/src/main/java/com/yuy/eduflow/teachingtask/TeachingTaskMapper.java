package com.yuy.eduflow.teachingtask;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classroom.Classroom;
import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Many;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Result;
import org.apache.ibatis.annotations.Results;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TeachingTaskMapper {

    @Select("""
            <script>
            SELECT t.id, t.course_id, t.primary_teacher_id, t.assistant_teacher_id,
                   t.classroom_id,
                   t.total_hours, t.notes, t.status,
                   t.created_at, t.updated_at,
                   c.id AS course_id2, c.name AS course_name,
                   pt.id AS pt_id, pt.name AS pt_name, pt.employee_no AS pt_employee_no, pt.department AS pt_dept,
                   at.id AS at_id, at.name AS at_name,
                   cr.id AS cr_id, cr.name AS cr_name, cr.building AS cr_building, cr.capacity AS cr_capacity, cr.classroom_type AS cr_classroom_type
            FROM teaching_task t
            LEFT JOIN course c ON t.course_id = c.id
            LEFT JOIN teacher pt ON t.primary_teacher_id = pt.id
            LEFT JOIN teacher at ON t.assistant_teacher_id = at.id
            LEFT JOIN classroom cr ON t.classroom_id = cr.id
            WHERE 1 = 1
            <if test='status != null and status != ""'>
              AND t.status = #{status}
            </if>
            <if test='courseId != null'>
              AND t.course_id = #{courseId}
            </if>
            <if test='teacherId != null'>
              AND (t.primary_teacher_id = #{teacherId} OR t.assistant_teacher_id = #{teacherId})
            </if>
            ORDER BY t.id DESC
            </script>
            """)
    @Results({
            @Result(property = "id", column = "id"),
            @Result(property = "courseId", column = "course_id"),
            @Result(property = "primaryTeacherId", column = "primary_teacher_id"),
            @Result(property = "assistantTeacherId", column = "assistant_teacher_id"),
            @Result(property = "classroomId", column = "classroom_id"),
            @Result(property = "totalHours", column = "total_hours"),
            @Result(property = "notes", column = "notes"),
            @Result(property = "status", column = "status"),
            @Result(property = "course.id", column = "course_id2"),
            @Result(property = "course.name", column = "course_name"),
            @Result(property = "primaryTeacher.id", column = "pt_id"),
            @Result(property = "primaryTeacher.name", column = "pt_name"),
            @Result(property = "primaryTeacher.employeeNo", column = "pt_employee_no"),
            @Result(property = "primaryTeacher.department", column = "pt_dept"),
            @Result(property = "assistantTeacher.id", column = "at_id"),
            @Result(property = "assistantTeacher.name", column = "at_name"),
            @Result(property = "classroom.id", column = "cr_id"),
            @Result(property = "classroom.name", column = "cr_name"),
            @Result(property = "classroom.building", column = "cr_building"),
            @Result(property = "classroom.capacity", column = "cr_capacity"),
            @Result(property = "classroom.classroomType", column = "cr_classroom_type"),
            @Result(property = "classGroups", column = "id", many = @Many(select = "findClassGroups")),
    })
    List<TeachingTask> findAll(
            @Param("status") String status,
            @Param("courseId") Long courseId,
            @Param("teacherId") Long teacherId);

    @Select("""
            SELECT t.id, t.course_id, t.primary_teacher_id, t.assistant_teacher_id,
                   t.classroom_id,
                   t.total_hours, t.notes, t.status,
                   t.created_at, t.updated_at,
                   c.id AS course_id2, c.name AS course_name,
                   pt.id AS pt_id, pt.name AS pt_name, pt.employee_no AS pt_employee_no, pt.department AS pt_dept,
                   at.id AS at_id, at.name AS at_name,
                   cr.id AS cr_id, cr.name AS cr_name, cr.building AS cr_building, cr.capacity AS cr_capacity, cr.classroom_type AS cr_classroom_type
            FROM teaching_task t
            LEFT JOIN course c ON t.course_id = c.id
            LEFT JOIN teacher pt ON t.primary_teacher_id = pt.id
            LEFT JOIN teacher at ON t.assistant_teacher_id = at.id
            LEFT JOIN classroom cr ON t.classroom_id = cr.id
            WHERE t.id = #{id}
            """)
    @Results({
            @Result(property = "id", column = "id"),
            @Result(property = "courseId", column = "course_id"),
            @Result(property = "primaryTeacherId", column = "primary_teacher_id"),
            @Result(property = "assistantTeacherId", column = "assistant_teacher_id"),
            @Result(property = "classroomId", column = "classroom_id"),
            @Result(property = "totalHours", column = "total_hours"),
            @Result(property = "notes", column = "notes"),
            @Result(property = "status", column = "status"),
            @Result(property = "course.id", column = "course_id2"),
            @Result(property = "course.name", column = "course_name"),
            @Result(property = "primaryTeacher.id", column = "pt_id"),
            @Result(property = "primaryTeacher.name", column = "pt_name"),
            @Result(property = "primaryTeacher.employeeNo", column = "pt_employee_no"),
            @Result(property = "primaryTeacher.department", column = "pt_dept"),
            @Result(property = "assistantTeacher.id", column = "at_id"),
            @Result(property = "assistantTeacher.name", column = "at_name"),
            @Result(property = "classroom.id", column = "cr_id"),
            @Result(property = "classroom.name", column = "cr_name"),
            @Result(property = "classroom.building", column = "cr_building"),
            @Result(property = "classroom.capacity", column = "cr_capacity"),
            @Result(property = "classroom.classroomType", column = "cr_classroom_type"),
    })
    TeachingTask findById(Long id);

    @Insert("""
            INSERT INTO teaching_task (
                course_id, primary_teacher_id, assistant_teacher_id, classroom_id,
                total_hours, notes, status
            )
            VALUES (
                #{courseId}, #{primaryTeacherId}, #{assistantTeacherId}, #{classroomId},
                #{totalHours}, #{notes}, #{status}
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
            SELECT cg.id, cg.name, cg.major, cg.grade, cg.student_count, cg.description
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
    @Select("""
            SELECT t.id, t.course_id, t.primary_teacher_id, t.assistant_teacher_id,
                   t.classroom_id,
                   t.total_hours, t.notes, t.status,
                   t.created_at, t.updated_at,
                   c.id AS course_id2, c.name AS course_name,
                   pt.id AS pt_id, pt.name AS pt_name, pt.employee_no AS pt_employee_no, pt.department AS pt_dept,
                   at.id AS at_id, at.name AS at_name,
                   cr.id AS cr_id, cr.name AS cr_name, cr.building AS cr_building, cr.capacity AS cr_capacity, cr.classroom_type AS cr_classroom_type
            FROM teaching_task t
            LEFT JOIN course c ON t.course_id = c.id
            LEFT JOIN teacher pt ON t.primary_teacher_id = pt.id
            LEFT JOIN teacher at ON t.assistant_teacher_id = at.id
            LEFT JOIN classroom cr ON t.classroom_id = cr.id
            WHERE t.id = #{id}
            """)
    @Results({
            @Result(property = "id", column = "id"),
            @Result(property = "courseId", column = "course_id"),
            @Result(property = "primaryTeacherId", column = "primary_teacher_id"),
            @Result(property = "assistantTeacherId", column = "assistant_teacher_id"),
            @Result(property = "classroomId", column = "classroom_id"),
            @Result(property = "totalHours", column = "total_hours"),
            @Result(property = "notes", column = "notes"),
            @Result(property = "status", column = "status"),
            @Result(property = "course.id", column = "course_id2"),
            @Result(property = "course.name", column = "course_name"),
            @Result(property = "primaryTeacher.id", column = "pt_id"),
            @Result(property = "primaryTeacher.name", column = "pt_name"),
            @Result(property = "primaryTeacher.employeeNo", column = "pt_employee_no"),
            @Result(property = "primaryTeacher.department", column = "pt_dept"),
            @Result(property = "assistantTeacher.id", column = "at_id"),
            @Result(property = "assistantTeacher.name", column = "at_name"),
            @Result(property = "classroom.id", column = "cr_id"),
            @Result(property = "classroom.name", column = "cr_name"),
            @Result(property = "classroom.building", column = "cr_building"),
            @Result(property = "classroom.capacity", column = "cr_capacity"),
            @Result(property = "classroom.classroomType", column = "cr_classroom_type"),
            @Result(property = "classGroups", column = "id", many = @Many(select = "findClassGroups")),
    })
    TeachingTask findWithDetails(Long id);
}
