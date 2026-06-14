package com.yuy.eduflow.management;

import com.yuy.eduflow.common.ApiResponse;
import java.util.Map;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/management/{entity}")
public class ManagementBatchController {

    private final ManagementBatchService service;

    public ManagementBatchController(ManagementBatchService service) {
        this.service = service;
    }

    @PostMapping("/batch-disable")
    public ApiResponse<Map<String, Integer>> disable(
            @PathVariable String entity,
            @RequestBody ManagementBatchRequest request) {
        return ApiResponse.success(Map.of("affected", service.disable(entity, request.ids())));
    }

    @PostMapping("/batch-delete")
    public ApiResponse<Map<String, Integer>> delete(
            @PathVariable String entity,
            @RequestBody ManagementBatchRequest request) {
        return ApiResponse.success(Map.of("affected", service.delete(entity, request.ids())));
    }
}
