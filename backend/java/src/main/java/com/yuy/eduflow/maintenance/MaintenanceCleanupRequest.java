package com.yuy.eduflow.maintenance;

public record MaintenanceCleanupRequest(
    String confirmText,
    String adminEmployeeNo,
    String adminPassword,
    String adminName
) {}
