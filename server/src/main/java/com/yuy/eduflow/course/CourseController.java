package com.yuy.eduflow.course;

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
@RequestMapping("/api/courses")
public class CourseController {
	private final CourseService courseService;

	public CourseController(CourseService courseService) {
		this.courseService = courseService;
	}

	@GetMapping
	public ApiResponse<List<Course>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(courseService.findAll(keyword, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<Course> findById(@PathVariable Long id) {
		return ApiResponse.success(courseService.findById(id));
	}

	@PostMapping
	public ApiResponse<Course> create(@RequestBody CourseRequest request) {
		return ApiResponse.success(courseService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<Course> update(@PathVariable Long id, @RequestBody CourseRequest request) {
		return ApiResponse.success(courseService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		courseService.delete(id);
		return ApiResponse.success();
	}
}
