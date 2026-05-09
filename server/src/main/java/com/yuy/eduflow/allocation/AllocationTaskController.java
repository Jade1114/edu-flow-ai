package com.yuy.eduflow.allocation;

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
@RequestMapping("/api/allocation-tasks")
public class AllocationTaskController {
	private final AllocationTaskService allocationTaskService;
	private final AllocationSchemeService allocationSchemeService;
	private final AllocationRagContextService allocationRagContextService;

	public AllocationTaskController(
		AllocationTaskService allocationTaskService,
		AllocationSchemeService allocationSchemeService,
		AllocationRagContextService allocationRagContextService
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationSchemeService = allocationSchemeService;
		this.allocationRagContextService = allocationRagContextService;
	}

	@GetMapping
	public ApiResponse<List<AllocationTask>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(allocationTaskService.findAll(keyword, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<AllocationTask> findById(@PathVariable Long id) {
		return ApiResponse.success(allocationTaskService.findById(id));
	}

	@GetMapping("/{id}/schemes")
	public ApiResponse<List<AllocationScheme>> findSchemes(@PathVariable Long id) {
		allocationTaskService.findById(id);
		return ApiResponse.success(allocationSchemeService.findAll(id, null));
	}

	@GetMapping("/{id}/rag-context")
	public ApiResponse<AllocationRagContext> buildRagContext(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationRagContextService.buildContext(id, topK));
	}

	@PostMapping
	public ApiResponse<AllocationTask> create(@RequestBody AllocationTaskRequest request) {
		return ApiResponse.success(allocationTaskService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<AllocationTask> update(@PathVariable Long id, @RequestBody AllocationTaskRequest request) {
		return ApiResponse.success(allocationTaskService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		allocationTaskService.delete(id);
		return ApiResponse.success();
	}
}
