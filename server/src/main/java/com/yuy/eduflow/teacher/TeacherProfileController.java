package com.yuy.eduflow.teacher;

import com.yuy.eduflow.common.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/teachers/{teacherId}/profile")
public class TeacherProfileController {
	private final TeacherProfileService teacherProfileService;

	public TeacherProfileController(TeacherProfileService teacherProfileService) {
		this.teacherProfileService = teacherProfileService;
	}

	@GetMapping
	public ApiResponse<TeacherProfile> findByTeacherId(@PathVariable Long teacherId) {
		return ApiResponse.success(teacherProfileService.findByTeacherId(teacherId));
	}

	@PutMapping
	public ApiResponse<TeacherProfile> save(
		@PathVariable Long teacherId,
		@RequestBody TeacherProfileRequest request
	) {
		return ApiResponse.success(teacherProfileService.save(teacherId, request));
	}
}
