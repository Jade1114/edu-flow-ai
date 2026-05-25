package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.conflict.ConflictDiagnosis;
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
	private final AllocationItemAdjustmentLogMapper adjustmentLogMapper;

	public AllocationSchemeController(
		AllocationSchemeService allocationSchemeService,
		AllocationItemService allocationItemService,
		AllocationSchemeConfirmService allocationSchemeConfirmService,
		AllocationItemAdjustmentLogMapper adjustmentLogMapper
	) {
		this.allocationSchemeService = allocationSchemeService;
		this.allocationItemService = allocationItemService;
		this.allocationSchemeConfirmService = allocationSchemeConfirmService;
		this.adjustmentLogMapper = adjustmentLogMapper;
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

	@GetMapping("/{id}/conflicts")
	public ApiResponse<ConflictDiagnosis> findConflicts(@PathVariable Long id) {
		allocationSchemeService.findById(id);
		return ApiResponse.success(allocationSchemeService.findConflictDiagnosis(id));
	}

	@PostMapping
	public ApiResponse<AllocationScheme> create(@RequestBody AllocationSchemeRequest request) {
		return ApiResponse.success(allocationSchemeService.create(request));
	}

	@PostMapping("/{id}/confirm")
	public ApiResponse<AllocationConfirmResult> confirm(@PathVariable Long id) {
		return ApiResponse.success(allocationSchemeConfirmService.confirm(id));
	}

	@PostMapping("/{id}/reevaluate")
	public ApiResponse<AllocationScheme> reevaluate(@PathVariable Long id) {
		return ApiResponse.success(allocationItemService.reevaluateScheme(id));
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

	@PostMapping("/{schemeId}/adjustment-log")
	public ApiResponse<Void> recordAdjustment(
		@PathVariable Long schemeId,
		@RequestBody AdjustmentLogRequest request
	) {
		AllocationItemAdjustmentLog log = new AllocationItemAdjustmentLog();
		log.setSchemeId(schemeId);
		log.setItemId(request.itemId());
		log.setTeachingTaskId(request.teachingTaskId());
		log.setFromTimeSlotId(request.fromTimeSlotId());
		log.setToTimeSlotId(request.toTimeSlotId());
		log.setFromClassroomId(request.fromClassroomId());
		log.setToClassroomId(request.toClassroomId());
		log.setReason(request.reason());
		adjustmentLogMapper.insert(log);
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
