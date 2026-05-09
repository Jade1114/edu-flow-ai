package com.yuy.eduflow.teacher;

import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.rag.TeacherProfileVectorService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/teachers/{teacherId}/profile")
public class TeacherProfileController {
	private final TeacherProfileService teacherProfileService;
	private final TeacherProfileVectorService teacherProfileVectorService;

	public TeacherProfileController(
		TeacherProfileService teacherProfileService,
		TeacherProfileVectorService teacherProfileVectorService
	) {
		this.teacherProfileService = teacherProfileService;
		this.teacherProfileVectorService = teacherProfileVectorService;
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

	@PostMapping("/vector-index")
	public ApiResponse<TeacherProfile> indexVector(@PathVariable Long teacherId) {
		return ApiResponse.success(teacherProfileVectorService.indexTeacherProfile(teacherId));
	}
}
