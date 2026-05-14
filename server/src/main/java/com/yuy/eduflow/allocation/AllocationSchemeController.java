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
@RequestMapping("/api/allocation-schemes")
public class AllocationSchemeController {
	private final AllocationSchemeService allocationSchemeService;
	private final AllocationItemService allocationItemService;
	private final AllocationSchemeConfirmService allocationSchemeConfirmService;

	public AllocationSchemeController(
		AllocationSchemeService allocationSchemeService,
		AllocationItemService allocationItemService,
		AllocationSchemeConfirmService allocationSchemeConfirmService
	) {
		this.allocationSchemeService = allocationSchemeService;
		this.allocationItemService = allocationItemService;
		this.allocationSchemeConfirmService = allocationSchemeConfirmService;
	}

	@GetMapping
	public ApiResponse<List<AllocationScheme>> findAll(
		@RequestParam(required = false) Long taskId,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(allocationSchemeService.findAll(taskId, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<AllocationScheme> findById(@PathVariable Long id) {
		return ApiResponse.success(allocationSchemeService.findById(id));
	}

	@GetMapping("/{id}/items")
	public ApiResponse<List<AllocationItemView>> findItems(@PathVariable Long id) {
		allocationSchemeService.findById(id);
		return ApiResponse.success(allocationItemService.findViewsBySchemeId(id));
	}

	@PostMapping
	public ApiResponse<AllocationScheme> create(@RequestBody AllocationSchemeRequest request) {
		return ApiResponse.success(allocationSchemeService.create(request));
	}

	@PostMapping("/{id}/confirm")
	public ApiResponse<AllocationConfirmResult> confirm(@PathVariable Long id) {
		return ApiResponse.success(allocationSchemeConfirmService.confirm(id));
	}

	@PutMapping("/{id}")
	public ApiResponse<AllocationScheme> update(@PathVariable Long id, @RequestBody AllocationSchemeRequest request) {
		return ApiResponse.success(allocationSchemeService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		allocationSchemeService.delete(id);
		return ApiResponse.success();
	}

	@PutMapping("/{schemeId}/items/{itemId}")
	public ApiResponse<List<AllocationItemView>> moveItem(
		@PathVariable Long schemeId,
		@PathVariable Long itemId,
		@RequestBody AllocationItemMoveRequest request
	) {
		return ApiResponse.success(allocationItemService.moveAndRecheck(schemeId, itemId, request));
	}

}
