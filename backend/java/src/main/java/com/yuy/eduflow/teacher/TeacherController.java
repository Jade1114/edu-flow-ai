package com.yuy.eduflow.teacher;

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
@RequestMapping("/api/teachers")
public class TeacherController {
	private final TeacherService teacherService;

	public TeacherController(TeacherService teacherService) {
		this.teacherService = teacherService;
	}

	@GetMapping
	public ApiResponse<Map<String, Object>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status,
		@RequestParam(defaultValue = "-1") int page,
		@RequestParam(defaultValue = "20") int size
	) {
		if (page < 0) {
			List<Teacher> all = teacherService.findAll(keyword, status);
			Map<String, Object> result = new LinkedHashMap<>();
			result.put("content", all);
			result.put("total", all.size());
			result.put("page", 0);
			result.put("size", all.size());
			return ApiResponse.success(result);
		}
		return ApiResponse.success(teacherService.findAllPaged(keyword, status, page, size));
	}

	@GetMapping("/{id}")
	public ApiResponse<Teacher> findById(@PathVariable Long id) {
		return ApiResponse.success(teacherService.findById(id));
	}

	@PostMapping
	public ApiResponse<Teacher> create(@RequestBody TeacherRequest request) {
		return ApiResponse.success(teacherService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<Teacher> update(@PathVariable Long id, @RequestBody TeacherRequest request) {
		return ApiResponse.success(teacherService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		teacherService.delete(id);
		return ApiResponse.success();
	}
}
