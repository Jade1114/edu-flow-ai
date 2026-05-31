package com.yuy.eduflow.course;

import com.yuy.eduflow.common.ApiResponse;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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
	public ApiResponse<Map<String, Object>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status,
		@RequestParam(defaultValue = "-1") int page,
		@RequestParam(defaultValue = "20") int size
	) {
		if (page < 0) {
			// page=-1: 返回全部（用于下拉框）
			List<Course> all = courseService.findAll(keyword, status);
			Map<String, Object> result = new LinkedHashMap<>();
			result.put("content", all);
			result.put("total", all.size());
			result.put("page", 0);
			result.put("size", all.size());
			return ApiResponse.success(result);
		}
		return ApiResponse.success(courseService.findAllPaged(keyword, status, page, size));
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
