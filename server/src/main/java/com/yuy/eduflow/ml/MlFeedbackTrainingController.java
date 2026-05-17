package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.ApiResponse;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ml/feedback")
public class MlFeedbackTrainingController {
    private final MlFeedbackTrainingService feedbackTrainingService;

    public MlFeedbackTrainingController(MlFeedbackTrainingService feedbackTrainingService) {
        this.feedbackTrainingService = feedbackTrainingService;
    }

    @GetMapping("/export")
    public ApiResponse<MlFeedbackExportResult> exportFeedback(@RequestParam(required = false) Long taskId) {
        return ApiResponse.success(feedbackTrainingService.exportFeedback(taskId));
    }

    @GetMapping("/latest-export")
    public ApiResponse<MlFeedbackExportResult> latestFeedbackExport(@RequestParam(required = false) Long taskId) {
        return ApiResponse.success(feedbackTrainingService.latestFeedbackExport(taskId));
    }

    @PostMapping("/train")
    public ApiResponse<MlTrainingStatusResult> train(@RequestParam(required = false) Long taskId) {
        return ApiResponse.success(feedbackTrainingService.train(taskId));
    }

    @GetMapping("/training-status")
    public ApiResponse<MlTrainingStatusResult> latestStatus() {
        return ApiResponse.success(feedbackTrainingService.latestStatus());
    }

    @GetMapping("/training-logs")
    public ApiResponse<List<Map<String, Object>>> trainingLogs(@RequestParam(defaultValue = "20") int limit) {
        return ApiResponse.success(feedbackTrainingService.getTrainingLogs(limit));
    }

    @GetMapping("/latest-training")
    public ApiResponse<Map<String, Object>> latestTraining() {
        return ApiResponse.success(feedbackTrainingService.getLatestTrainingLog());
    }
}
