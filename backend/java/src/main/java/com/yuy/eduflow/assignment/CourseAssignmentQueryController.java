package com.yuy.eduflow.assignment;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CourseAssignmentQueryController {
	private final CourseAssignmentService courseAssignmentService;

	public CourseAssignmentQueryController(CourseAssignmentService courseAssignmentService) {
		this.courseAssignmentService = courseAssignmentService;
	}

	@GetMapping("/api/teachers/{teacherId}/course-assignments")
	public ApiResponse<List<CourseAssignmentView>> findTeacherAssignments(
		@PathVariable Long teacherId,
		@RequestParam(required = false) Integer weekNumber,
		@RequestParam(required = false) Integer dayOfWeek
	) {
		return ApiResponse.success(courseAssignmentService.findTeacherAssignments(teacherId, weekNumber, dayOfWeek));
	}

	@GetMapping("/api/class-groups/{classGroupId}/course-assignments")
	public ApiResponse<List<CourseAssignmentView>> findClassGroupAssignments(
		@PathVariable Long classGroupId,
		@RequestParam(required = false) Integer weekNumber,
		@RequestParam(required = false) Integer dayOfWeek
	) {
		return ApiResponse.success(courseAssignmentService.findClassGroupAssignments(classGroupId, weekNumber, dayOfWeek));
	}
}
