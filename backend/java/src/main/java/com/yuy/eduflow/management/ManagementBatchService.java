package com.yuy.eduflow.management;

import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.enums.ActiveStatus;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ManagementBatchService {

    private static final Map<String, EntityTarget> TARGETS = Map.of(
            "teachers", new EntityTarget("teacher", true),
            "classrooms", new EntityTarget("classroom", true),
            "courses", new EntityTarget("course", true),
            "class-groups", new EntityTarget("class_group", false),
            "teaching-tasks", new EntityTarget("teaching_task", true)
    );

    private final ManagementBatchMapper mapper;

    public ManagementBatchService(ManagementBatchMapper mapper) {
        this.mapper = mapper;
    }

    @Transactional
    public int disable(String entity, List<Long> ids) {
        EntityTarget target = target(entity);
        if (!target.disableSupported()) {
            throw new ValidationException("该数据类型暂不支持禁用");
        }
        List<Long> normalizedIds = normalizeIds(ids);
        return mapper.updateStatus(target.tableName(), normalizedIds, ActiveStatus.INACTIVE.code());
    }

    @Transactional
    public int delete(String entity, List<Long> ids) {
        EntityTarget target = target(entity);
        List<Long> normalizedIds = normalizeIds(ids);
        if ("teaching_task".equals(target.tableName())) {
            deleteTeachingTaskDependencies(normalizedIds);
        }
        if ("course".equals(target.tableName())) {
            List<Long> teachingTaskIds = mapper.findTeachingTaskIdsByCourseIds(normalizedIds);
            if (!teachingTaskIds.isEmpty()) {
                deleteTeachingTasks(teachingTaskIds);
            }
        }
        if ("teacher".equals(target.tableName())) {
            List<Long> teachingTaskIds = mapper.findTeachingTaskIdsByTeacherIds(normalizedIds);
            if (!teachingTaskIds.isEmpty()) {
                deleteTeachingTasks(teachingTaskIds);
            }
            mapper.deleteTeacherProfiles(normalizedIds);
        }
        return mapper.deleteRows(target.tableName(), normalizedIds);
    }

    private void deleteTeachingTasks(List<Long> ids) {
        deleteTeachingTaskDependencies(ids);
        mapper.deleteRows("teaching_task", ids);
    }

    private void deleteTeachingTaskDependencies(List<Long> ids) {
        mapper.detachConflictCheckResults(ids);
        mapper.detachMlFeedbackEvents(ids);
        mapper.deleteAllocationTaskTeachingTasks(ids);
        mapper.deleteAllocationItemAdjustmentLogs(ids);
        mapper.deleteAllocationItems(ids);
        mapper.deleteAdjustmentRequestsByTeachingTasks(ids);
        mapper.deleteCourseAssignments(ids);
    }

    private EntityTarget target(String entity) {
        EntityTarget target = TARGETS.get(entity);
        if (target == null) {
            throw new ValidationException("不支持的管理数据类型: " + entity);
        }
        return target;
    }

    private List<Long> normalizeIds(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            throw new ValidationException("请选择要处理的数据");
        }
        List<Long> normalized = ids.stream()
                .filter(id -> id != null && id > 0)
                .distinct()
                .toList();
        if (normalized.isEmpty()) {
            throw new ValidationException("请选择有效的数据");
        }
        return normalized;
    }

    private record EntityTarget(String tableName, boolean disableSupported) {
    }
}
