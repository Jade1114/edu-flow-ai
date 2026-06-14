package com.yuy.eduflow.maintenance;

import com.yuy.eduflow.common.exception.ValidationException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class MaintenanceCleanupService {
    private static final String CONFIRM_TEXT = "清理测试数据";

    private final MaintenanceCleanupMapper mapper;

    public MaintenanceCleanupService(MaintenanceCleanupMapper mapper) {
        this.mapper = mapper;
    }

    public Map<String, Object> cleanupTestData(MaintenanceCleanupRequest request) {
        if (request == null || !CONFIRM_TEXT.equals(request.confirmText())) {
            throw new ValidationException("确认文本不正确，请输入：" + CONFIRM_TEXT);
        }
        String employeeNo = defaultString(request.adminEmployeeNo(), "admin");
        String password = defaultString(request.adminPassword(), "admin123");
        String name = defaultString(request.adminName(), "系统管理员");

        mapper.setForeignKeyChecks(0);
        try {
            truncateAll();
            mapper.insertAdmin(employeeNo, password, name);
        } finally {
            mapper.setForeignKeyChecks(1);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", "ok");
        result.put("adminEmployeeNo", employeeNo);
        result.put("adminName", name);
        result.put("counts", mapper.countCoreTables());
        result.put("clearedTables", clearedTables());
        return result;
    }

    private void truncateAll() {
        truncateIfExists("allocation_item_adjustment_log", mapper::truncateAllocationItemAdjustmentLog);
        truncateIfExists("adjustment_request", mapper::truncateAdjustmentRequest);
        truncateIfExists("conflict_check_result", mapper::truncateConflictCheckResult);
        truncateIfExists("course_assignment", mapper::truncateCourseAssignment);
        truncateIfExists("allocation_scheme_feedback", mapper::truncateAllocationSchemeFeedback);
        truncateIfExists("ml_feedback_event", mapper::truncateMlFeedbackEvent);
        truncateIfExists("model_training_log", mapper::truncateModelTrainingLog);
        truncateIfExists("allocation_item", mapper::truncateAllocationItem);
        truncateIfExists("allocation_scheme", mapper::truncateAllocationScheme);
        truncateIfExists("allocation_task_generation_config", mapper::truncateAllocationTaskGenerationConfig);
        truncateIfExists("allocation_task_teaching_task", mapper::truncateAllocationTaskTeachingTask);
        truncateIfExists("allocation_task", mapper::truncateAllocationTask);
        truncateIfExists("schedule_template_fragment_slot", mapper::truncateScheduleTemplateFragmentSlot);
        truncateIfExists("schedule_template_week", mapper::truncateScheduleTemplateWeek);
        truncateIfExists("schedule_template_fragment", mapper::truncateScheduleTemplateFragment);
        truncateIfExists("schedule_template", mapper::truncateScheduleTemplate);
        truncateIfExists("teaching_task_classroom", mapper::truncateTeachingTaskClassroom);
        truncateIfExists("teaching_task_class_group", mapper::truncateTeachingTaskClassGroup);
        truncateIfExists("teaching_task", mapper::truncateTeachingTask);
        truncateIfExists("teacher_profile", mapper::truncateTeacherProfile);
        truncateIfExists("course", mapper::truncateCourse);
        truncateIfExists("classroom", mapper::truncateClassroom);
        truncateIfExists("class_group", mapper::truncateClassGroup);
        truncateIfExists("teacher", mapper::truncateTeacher);
    }

    private void truncateIfExists(String tableName, Runnable truncate) {
        if (mapper.tableExists(tableName) > 0) {
            truncate.run();
        }
    }

    private List<String> clearedTables() {
        return List.of(
            "allocation_item_adjustment_log",
            "adjustment_request",
            "conflict_check_result",
            "course_assignment",
            "allocation_scheme_feedback",
            "ml_feedback_event",
            "model_training_log",
            "allocation_item",
            "allocation_scheme",
            "allocation_task_generation_config",
            "allocation_task_teaching_task",
            "allocation_task",
            "schedule_template_fragment_slot",
            "schedule_template_week",
            "schedule_template_fragment",
            "schedule_template",
            "teaching_task_classroom",
            "teaching_task_class_group",
            "teaching_task",
            "teacher_profile",
            "course",
            "classroom",
            "class_group",
            "teacher"
        );
    }

    private String defaultString(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
