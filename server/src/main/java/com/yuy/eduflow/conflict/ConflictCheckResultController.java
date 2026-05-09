package com.yuy.eduflow.conflict;

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
@RequestMapping("/api/conflict-check-results")
public class ConflictCheckResultController {
	private final ConflictCheckResultService conflictCheckResultService;

	public ConflictCheckResultController(ConflictCheckResultService conflictCheckResultService) {
		this.conflictCheckResultService = conflictCheckResultService;
	}

	@GetMapping
	public ApiResponse<List<ConflictCheckResult>> findAll(
		@RequestParam(required = false) String bizType,
		@RequestParam(required = false) Long bizId,
		@RequestParam(required = false) String conflictType,
		@RequestParam(required = false) Boolean resolved
	) {
		return ApiResponse.success(conflictCheckResultService.findAll(bizType, bizId, conflictType, resolved));
	}

	@GetMapping("/{id}")
	public ApiResponse<ConflictCheckResult> findById(@PathVariable Long id) {
		return ApiResponse.success(conflictCheckResultService.findById(id));
	}

	@PostMapping
	public ApiResponse<ConflictCheckResult> create(@RequestBody ConflictCheckResultRequest request) {
		return ApiResponse.success(conflictCheckResultService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<ConflictCheckResult> update(
		@PathVariable Long id,
		@RequestBody ConflictCheckResultRequest request
	) {
		return ApiResponse.success(conflictCheckResultService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		conflictCheckResultService.delete(id);
		return ApiResponse.success();
	}
}
