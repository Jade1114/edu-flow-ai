package com.yuy.eduflow.teachingtask;

import com.yuy.eduflow.common.ApiResponse;
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
@RequestMapping("/api/teaching-tasks")
public class TeachingTaskController {
    private final TeachingTaskService teachingTaskService;

    public TeachingTaskController(TeachingTaskService teachingTaskService) {
        this.teachingTaskService = teachingTaskService;
    }

    @GetMapping
    public ApiResponse<Map<String, Object>> findAll(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long courseId,
            @RequestParam(required = false) Long teacherId,
            @RequestParam(required = false) String courseType,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "-1") int page,
            @RequestParam(defaultValue = "20") int size) {
        if (page < 0) {
            List<TeachingTask> all = teachingTaskService.findAll(status, courseId, teacherId, courseType, keyword);
            return ApiResponse.success(Map.of("content", all, "total", all.size(), "page", 0, "size", all.size()));
        }
        return ApiResponse.success(teachingTaskService.findAllPaged(status, courseId, teacherId, courseType, keyword, page, size));
    }

    @GetMapping("/{id}")
    public ApiResponse<TeachingTask> findById(@PathVariable Long id) {
        return ApiResponse.success(teachingTaskService.findById(id));
    }

    @PostMapping
    public ApiResponse<TeachingTask> create(@RequestBody TeachingTaskRequest request) {
        return ApiResponse.success(teachingTaskService.create(request));
    }

    @PutMapping("/{id}")
    public ApiResponse<TeachingTask> update(@PathVariable Long id, @RequestBody TeachingTaskRequest request) {
        return ApiResponse.success(teachingTaskService.update(id, request));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        teachingTaskService.delete(id);
        return ApiResponse.success();
    }
}
