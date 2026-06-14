package com.yuy.eduflow.importreview;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

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

    @GetMapping("/items")
    public ApiResponse<List<ImportReviewItem>> findAllItems() {
        return ApiResponse.success(importReviewService.findAllItems());
    }

    @PutMapping("/items")
    public ApiResponse<Map<String, Object>> saveAllItems(@RequestBody ImportReviewSaveRequest request) {
        return ApiResponse.success(importReviewService.saveAllItems(request));
    }

    @PostMapping("/apply-all")
    public ApiResponse<Map<String, Object>> applyAll(@RequestBody ImportReviewApplyRequest request) {
        return ApiResponse.success(importReviewService.applyAll(request));
    }

    @DeleteMapping("/batches")
    public ApiResponse<Map<String, Object>> deleteAllBatches() {
        return ApiResponse.success(importReviewService.deleteAllBatches());
    }

    @GetMapping("/batches/{batchId}/items")
    public ApiResponse<List<ImportReviewItem>> findItems(@PathVariable String batchId) {
        return ApiResponse.success(importReviewService.findItems(batchId));
    }

    @GetMapping("/process-folder/stream")
    public SseEmitter processFolderStream(
        @RequestParam String rawDir,
        @RequestParam(defaultValue = "TEST_2025_2026_2") String taskBatch,
        @RequestParam(defaultValue = "false") boolean clearExisting
    ) {
        return importReviewService.processFolderStream(rawDir, taskBatch, clearExisting);
    }

    @PutMapping("/batches/{batchId}/items")
    public ApiResponse<Map<String, Object>> saveItems(@PathVariable String batchId, @RequestBody ImportReviewSaveRequest request) {
        return ApiResponse.success(importReviewService.saveItems(batchId, request));
    }

    @PostMapping("/batches/{batchId}/apply")
    public ApiResponse<Map<String, Object>> apply(@PathVariable String batchId, @RequestBody ImportReviewApplyRequest request) {
        return ApiResponse.success(importReviewService.apply(batchId, request));
    }

    @DeleteMapping("/batches/{batchId}")
    public ApiResponse<Map<String, Object>> deleteBatch(@PathVariable String batchId) {
        return ApiResponse.success(importReviewService.deleteBatch(batchId));
    }
}
