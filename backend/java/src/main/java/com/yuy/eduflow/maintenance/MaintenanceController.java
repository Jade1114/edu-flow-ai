package com.yuy.eduflow.maintenance;

import com.yuy.eduflow.common.ApiResponse;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/maintenance")
public class MaintenanceController {
    private final MaintenanceCleanupService cleanupService;

    public MaintenanceController(MaintenanceCleanupService cleanupService) {
        this.cleanupService = cleanupService;
    }

    @PostMapping("/cleanup-test-data")
    public ApiResponse<Map<String, Object>> cleanupTestData(@RequestBody MaintenanceCleanupRequest request) {
        return ApiResponse.success(cleanupService.cleanupTestData(request));
    }
}
