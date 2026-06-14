package com.yuy.eduflow.management;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ManagementBatchMapper {

    @Update("""
            <script>
            UPDATE ${tableName}
            SET status = #{status}
            WHERE id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int updateStatus(@Param("tableName") String tableName, @Param("ids") List<Long> ids, @Param("status") String status);

    @Select("""
            <script>
            SELECT id
            FROM teaching_task
            WHERE course_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    List<Long> findTeachingTaskIdsByCourseIds(@Param("ids") List<Long> ids);

    @Select("""
            <script>
            SELECT id
            FROM teaching_task
            WHERE primary_teacher_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            OR assistant_teacher_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    List<Long> findTeachingTaskIdsByTeacherIds(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM ${tableName}
            WHERE id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteRows(@Param("tableName") String tableName, @Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM allocation_task_teaching_task
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteAllocationTaskTeachingTasks(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM allocation_item_adjustment_log
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteAllocationItemAdjustmentLogs(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM allocation_item
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteAllocationItems(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM adjustment_request
            WHERE assignment_id IN (
                SELECT id FROM course_assignment
                WHERE teaching_task_id IN
                <foreach collection="ids" item="id" open="(" separator="," close=")">
                    #{id}
                </foreach>
            )
            </script>
            """)
    int deleteAdjustmentRequestsByTeachingTasks(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM course_assignment
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteCourseAssignments(@Param("ids") List<Long> ids);

    @Update("""
            <script>
            UPDATE conflict_check_result
            SET teaching_task_id = NULL
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int detachConflictCheckResults(@Param("ids") List<Long> ids);

    @Update("""
            <script>
            UPDATE ml_feedback_event
            SET teaching_task_id = NULL
            WHERE teaching_task_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int detachMlFeedbackEvents(@Param("ids") List<Long> ids);

    @Delete("""
            <script>
            DELETE FROM teacher_profile
            WHERE teacher_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">
                #{id}
            </foreach>
            </script>
            """)
    int deleteTeacherProfiles(@Param("ids") List<Long> ids);
}
