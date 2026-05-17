package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/adjustment-requests")
public class AdjustmentRequestController {

    private final AdjustmentRequestService adjustmentRequestService;

    public AdjustmentRequestController(AdjustmentRequestService adjustmentRequestService) {
        this.adjustmentRequestService = adjustmentRequestService;
    }

    @GetMapping
    public ApiResponse<List<AdjustmentRequest>> findAll(
        @RequestParam(required = false) String status,
        @RequestParam(required = false) Long teacherId
    ) {
        return ApiResponse.success(adjustmentRequestService.findAll(status, teacherId));
    }

    @GetMapping("/{id}")
    public ApiResponse<AdjustmentRequest> findById(@PathVariable Long id) {
        return ApiResponse.success(adjustmentRequestService.findById(id));
    }

    @PostMapping
    public ApiResponse<AdjustmentRequest> create(@RequestBody AdjustmentRequestRequest request) {
        return ApiResponse.success(adjustmentRequestService.create(request));
    }

    @PostMapping("/{id}/confirm")
    public ApiResponse<Void> confirm(
        @PathVariable Long id,
        @RequestBody AdjustmentConfirmRequest request
    ) {
        adjustmentRequestService.confirm(id, request);
        return ApiResponse.success();
    }

    @PostMapping("/{id}/reject")
    public ApiResponse<Void> reject(
        @PathVariable Long id,
        @RequestBody AdjustmentRejectRequest request
    ) {
        adjustmentRequestService.reject(id, request);
        return ApiResponse.success();
    }
}
