package com.yuy.eduflow.allocation;

public record AllocationItemMoveRequest(
    Long classroomId,
    Long timeSlotId,
    String reason
) {
}
