package com.yuy.eduflow.adjustment;

import java.util.List;

public record AdjustmentRequestRequest(
    Long assignmentId,
    String reason,
    String preferredTimeText
) {}
