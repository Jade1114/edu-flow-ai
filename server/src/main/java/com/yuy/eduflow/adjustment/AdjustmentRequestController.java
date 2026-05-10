package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/adjustment-requests")
public class AdjustmentRequestController {
	private final AdjustmentRequestService adjustmentRequestService;
	private final AdjustmentSuggestionGenerationService adjustmentSuggestionGenerationService;
	private final AdjustmentSuggestionConfirmService adjustmentSuggestionConfirmService;

	public AdjustmentRequestController(
		AdjustmentRequestService adjustmentRequestService,
		AdjustmentSuggestionGenerationService adjustmentSuggestionGenerationService,
		AdjustmentSuggestionConfirmService adjustmentSuggestionConfirmService
	) {
		this.adjustmentRequestService = adjustmentRequestService;
		this.adjustmentSuggestionGenerationService = adjustmentSuggestionGenerationService;
		this.adjustmentSuggestionConfirmService = adjustmentSuggestionConfirmService;
	}

	@GetMapping
	public ApiResponse<List<AdjustmentRequest>> findAll(
		@RequestParam(required = false) Long assignmentId,
		@RequestParam(required = false) Long teacherId,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(adjustmentRequestService.findAll(assignmentId, teacherId, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<AdjustmentRequest> findById(@PathVariable Long id) {
		return ApiResponse.success(adjustmentRequestService.findById(id));
	}

	@PostMapping
	public ApiResponse<AdjustmentRequest> create(@RequestBody AdjustmentRequestRequest request) {
		return ApiResponse.success(adjustmentRequestService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<AdjustmentRequest> update(@PathVariable Long id, @RequestBody AdjustmentRequestRequest request) {
		return ApiResponse.success(adjustmentRequestService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		adjustmentRequestService.delete(id);
		return ApiResponse.success();
	}

	@PostMapping("/{id}/suggestions")
	public ApiResponse<AdjustmentSuggestionPreview> generateSuggestions(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(adjustmentSuggestionGenerationService.generateSuggestions(id, topK));
	}

	@PostMapping("/{id}/confirm")
	public ApiResponse<AdjustmentConfirmResult> confirm(
		@PathVariable Long id,
		@RequestBody AdjustmentConfirmRequest request
	) {
		return ApiResponse.success(adjustmentSuggestionConfirmService.confirm(id, request));
	}

	@PostMapping("/{id}/reject")
	public ApiResponse<AdjustmentRequest> reject(
		@PathVariable Long id,
		@RequestBody(required = false) AdjustmentRejectRequest request
	) {
		return ApiResponse.success(adjustmentSuggestionConfirmService.reject(id, request));
	}
}
