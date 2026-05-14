package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.enums.AdjustmentStatus;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class AdjustmentRequest {
    private Long id;
    private Long assignmentId;
    private Long teacherId;
    private String reason;
    private String preferredTimeText;
    private String aiSuggestion;
    private AdjustmentStatus status;
    private String reviewNote;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
