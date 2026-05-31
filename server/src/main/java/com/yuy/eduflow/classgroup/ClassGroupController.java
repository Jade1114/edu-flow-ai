package com.yuy.eduflow.classgroup;

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
@RequestMapping("/api/class-groups")
public class ClassGroupController {
	private final ClassGroupService classGroupService;

	public ClassGroupController(ClassGroupService classGroupService) {
		this.classGroupService = classGroupService;
	}

	@GetMapping
	public ApiResponse<Map<String, Object>> findAll(
			@RequestParam(required = false) String keyword,
			@RequestParam(defaultValue = "-1") int page,
			@RequestParam(defaultValue = "20") int size) {
		if (page < 0) {
			List<ClassGroup> all = classGroupService.findAll(keyword);
			Map<String, Object> result = new LinkedHashMap<>();
			result.put("content", all);
			result.put("total", all.size());
			result.put("page", 0);
			result.put("size", all.size());
			return ApiResponse.success(result);
		}
		return ApiResponse.success(classGroupService.findAllPaged(keyword, page, size));
	}

	@GetMapping("/{id}")
	public ApiResponse<ClassGroup> findById(@PathVariable Long id) {
		return ApiResponse.success(classGroupService.findById(id));
	}

	@PostMapping
	public ApiResponse<ClassGroup> create(@RequestBody ClassGroupRequest request) {
		return ApiResponse.success(classGroupService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<ClassGroup> update(@PathVariable Long id, @RequestBody ClassGroupRequest request) {
		return ApiResponse.success(classGroupService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		classGroupService.delete(id);
		return ApiResponse.success();
	}
}
