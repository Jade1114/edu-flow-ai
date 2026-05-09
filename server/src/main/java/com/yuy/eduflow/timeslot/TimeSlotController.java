package com.yuy.eduflow.timeslot;

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
@RequestMapping("/api/time-slots")
public class TimeSlotController {
	private final TimeSlotService timeSlotService;

	public TimeSlotController(TimeSlotService timeSlotService) {
		this.timeSlotService = timeSlotService;
	}

	@GetMapping
	public ApiResponse<List<TimeSlot>> findAll(
		@RequestParam(required = false) Integer weekNumber,
		@RequestParam(required = false) Integer dayOfWeek
	) {
		return ApiResponse.success(timeSlotService.findAll(weekNumber, dayOfWeek));
	}

	@GetMapping("/{id}")
	public ApiResponse<TimeSlot> findById(@PathVariable Long id) {
		return ApiResponse.success(timeSlotService.findById(id));
	}

	@PostMapping
	public ApiResponse<TimeSlot> create(@RequestBody TimeSlotRequest request) {
		return ApiResponse.success(timeSlotService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<TimeSlot> update(@PathVariable Long id, @RequestBody TimeSlotRequest request) {
		return ApiResponse.success(timeSlotService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		timeSlotService.delete(id);
		return ApiResponse.success();
	}
}
