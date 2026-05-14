package com.yuy.eduflow.allocation;

import com.yuy.eduflow.enums.ActiveStatus;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AllocationTaskTeachingTaskResult {
    private Long id;
    private Long courseId;
    private Long primaryTeacherId;
    private Long assistantTeacherId;
    private Integer totalHours;
    private Long classroomId;
    private String notes;
    private ActiveStatus status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    // 关联查询字段（非 DB 列）
    private String courseName;
    private String primaryTeacherName;
    private String assistantTeacherName;
}
