package com.yuy.eduflow.adjustment;

public record AdjustmentConfirmResult(
    Long requestId,
    int candidateIndex,
    String summary
) {}
