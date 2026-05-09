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
@RequestMapping("/api/allocation-items")
public class AllocationItemController {
	private final AllocationItemService allocationItemService;

	public AllocationItemController(AllocationItemService allocationItemService) {
		this.allocationItemService = allocationItemService;
	}

	@GetMapping
	public ApiResponse<List<AllocationItem>> findAll(
		@RequestParam(required = false) Long schemeId,
		@RequestParam(required = false) Long teacherId,
		@RequestParam(required = false) Long classGroupId,
		@RequestParam(required = false) Long classroomId,
		@RequestParam(required = false) Long timeSlotId
	) {
		return ApiResponse.success(
			allocationItemService.findAll(schemeId, teacherId, classGroupId, classroomId, timeSlotId)
		);
	}

	@GetMapping("/{id}")
	public ApiResponse<AllocationItem> findById(@PathVariable Long id) {
		return ApiResponse.success(allocationItemService.findById(id));
	}

	@PostMapping
	public ApiResponse<AllocationItem> create(@RequestBody AllocationItemRequest request) {
		return ApiResponse.success(allocationItemService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<AllocationItem> update(@PathVariable Long id, @RequestBody AllocationItemRequest request) {
		return ApiResponse.success(allocationItemService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		allocationItemService.delete(id);
		return ApiResponse.success();
	}
}
