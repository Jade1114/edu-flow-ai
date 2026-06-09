package com.yuy.eduflow.importreview;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/import-reviews")
public class ImportReviewController {
    private final ImportReviewService importReviewService;

    public ImportReviewController(ImportReviewService importReviewService) {
        this.importReviewService = importReviewService;
    }

    @GetMapping("/batches")
    public ApiResponse<List<ImportReviewBatch>> findBatches() {
        return ApiResponse.success(importReviewService.findBatches());
    }

    @GetMapping("/batches/{batchId}/items")
    public ApiResponse<List<ImportReviewItem>> findItems(@PathVariable String batchId) {
        return ApiResponse.success(importReviewService.findItems(batchId));
    }

    @PutMapping("/batches/{batchId}/items")
    public ApiResponse<Map<String, Object>> saveItems(@PathVariable String batchId, @RequestBody ImportReviewSaveRequest request) {
        return ApiResponse.success(importReviewService.saveItems(batchId, request));
    }
}
