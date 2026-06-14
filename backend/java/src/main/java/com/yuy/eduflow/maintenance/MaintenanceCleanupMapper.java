package com.yuy.eduflow.maintenance;

import java.util.List;
import java.util.Map;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface MaintenanceCleanupMapper {
    @Update("SET FOREIGN_KEY_CHECKS = #{enabled}")
    void setForeignKeyChecks(@Param("enabled") int enabled);

    @Select("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = #{tableName}")
    int tableExists(@Param("tableName") String tableName);

    @Update("TRUNCATE TABLE allocation_item_adjustment_log")
    void truncateAllocationItemAdjustmentLog();

    @Update("TRUNCATE TABLE adjustment_request")
    void truncateAdjustmentRequest();

    @Update("TRUNCATE TABLE conflict_check_result")
    void truncateConflictCheckResult();

    @Update("TRUNCATE TABLE course_assignment")
    void truncateCourseAssignment();

    @Update("TRUNCATE TABLE allocation_scheme_feedback")
    void truncateAllocationSchemeFeedback();

    @Update("TRUNCATE TABLE ml_feedback_event")
    void truncateMlFeedbackEvent();

    @Update("TRUNCATE TABLE model_training_log")
    void truncateModelTrainingLog();

    @Update("TRUNCATE TABLE allocation_item")
    void truncateAllocationItem();

    @Update("TRUNCATE TABLE allocation_scheme")
    void truncateAllocationScheme();

    @Update("TRUNCATE TABLE allocation_task_generation_config")
    void truncateAllocationTaskGenerationConfig();

    @Update("TRUNCATE TABLE allocation_task_teaching_task")
    void truncateAllocationTaskTeachingTask();

    @Update("TRUNCATE TABLE allocation_task")
    void truncateAllocationTask();

    @Update("TRUNCATE TABLE schedule_template_fragment_slot")
    void truncateScheduleTemplateFragmentSlot();

    @Update("TRUNCATE TABLE schedule_template_week")
    void truncateScheduleTemplateWeek();

    @Update("TRUNCATE TABLE schedule_template_fragment")
    void truncateScheduleTemplateFragment();

    @Update("TRUNCATE TABLE schedule_template")
    void truncateScheduleTemplate();

    @Update("TRUNCATE TABLE teaching_task_classroom")
    void truncateTeachingTaskClassroom();

    @Update("TRUNCATE TABLE teaching_task_class_group")
    void truncateTeachingTaskClassGroup();

    @Update("TRUNCATE TABLE teaching_task")
    void truncateTeachingTask();

    @Update("TRUNCATE TABLE teacher_profile")
    void truncateTeacherProfile();

    @Update("TRUNCATE TABLE course")
    void truncateCourse();

    @Update("TRUNCATE TABLE classroom")
    void truncateClassroom();

    @Update("TRUNCATE TABLE class_group")
    void truncateClassGroup();

    @Update("TRUNCATE TABLE teacher")
    void truncateTeacher();

    @Insert("""
        INSERT INTO teacher (employee_no, password, role, name, department, title, status)
        VALUES (#{employeeNo}, #{password}, 'ADMIN', #{name}, '系统管理', '管理员', 'ACTIVE')
        """)
    int insertAdmin(@Param("employeeNo") String employeeNo, @Param("password") String password, @Param("name") String name);

    @Select("""
        SELECT 'course' AS table_name, COUNT(*) AS row_count FROM course
        UNION ALL SELECT 'teacher', COUNT(*) FROM teacher
        UNION ALL SELECT 'classroom', COUNT(*) FROM classroom
        UNION ALL SELECT 'class_group', COUNT(*) FROM class_group
        UNION ALL SELECT 'teaching_task', COUNT(*) FROM teaching_task
        UNION ALL SELECT 'allocation_task', COUNT(*) FROM allocation_task
        """)
    List<Map<String, Object>> countCoreTables();
}
