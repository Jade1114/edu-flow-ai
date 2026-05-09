package com.yuy.eduflow.classroom;

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
@RequestMapping("/api/classrooms")
public class ClassroomController {
	private final ClassroomService classroomService;

	public ClassroomController(ClassroomService classroomService) {
		this.classroomService = classroomService;
	}

	@GetMapping
	public ApiResponse<List<Classroom>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(classroomService.findAll(keyword, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<Classroom> findById(@PathVariable Long id) {
		return ApiResponse.success(classroomService.findById(id));
	}

	@PostMapping
	public ApiResponse<Classroom> create(@RequestBody ClassroomRequest request) {
		return ApiResponse.success(classroomService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<Classroom> update(@PathVariable Long id, @RequestBody ClassroomRequest request) {
		return ApiResponse.success(classroomService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		classroomService.delete(id);
		return ApiResponse.success();
	}
}
