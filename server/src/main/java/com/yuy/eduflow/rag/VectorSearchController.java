package com.yuy.eduflow.rag;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/vector-store")
public class VectorSearchController {
	private final TeacherProfileVectorService teacherProfileVectorService;

	public VectorSearchController(TeacherProfileVectorService teacherProfileVectorService) {
		this.teacherProfileVectorService = teacherProfileVectorService;
	}

	@PostMapping("/search")
	public ApiResponse<List<VectorSearchResult>> search(@RequestBody VectorSearchRequest request) {
		return ApiResponse.success(teacherProfileVectorService.search(
			request.query(),
			request.topK(),
			request.status()
		));
	}
}
