package com.yuy.eduflow.dataimport;

import com.yuy.eduflow.common.ApiResponse;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/data-import")
public class RealDataImportController {
    private final RealDataImportService realDataImportService;

    public RealDataImportController(RealDataImportService realDataImportService) {
        this.realDataImportService = realDataImportService;
    }

    @PostMapping("/real-dataset")
    public ApiResponse<RealDataImportResult> importRealDataset() {
        return ApiResponse.success(realDataImportService.importCleanDataset());
    }
}
