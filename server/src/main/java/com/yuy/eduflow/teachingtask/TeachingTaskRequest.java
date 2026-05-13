package com.yuy.eduflow.teachingtask;

import java.util.List;

public record TeachingTaskRequest(
        Long courseId,
        Long primaryTeacherId,
        Long assistantTeacherId,
        Long classroomId,
        Integer totalHours,
        String notes,
        String status,
        List<Long> classGroupIds) {
}
