package com.yuy.eduflow.conflict;

import java.util.List;
import java.util.Map;

/**
 * 方案冲突诊断报告，前端直接消费。
 */
public record ConflictDiagnosis(
    String summary,
    int total,
    boolean clean,
    Map<String, List<ConflictDiagnosisItem>> groups,
    List<ConflictDiagnosisItem> hoursMismatch
) {
    public record ConflictDiagnosisItem(
        Long id,
        String bizType,
        Long bizId,
        String conflictType,
        String typeLabel,
        String message,
        Long relatedTeacherId,
        String relatedTeacherName,
        Long relatedClassGroupId,
        String relatedClassGroupName,
        Long relatedClassroomId,
        String relatedClassroomName,
        Long relatedTimeSlotId,
        String relatedTimeSlotLabel,
        Long teachingTaskId,
        String courseName,
        Integer expectedHours,
        Integer actualHours
    ) {
    }
}
