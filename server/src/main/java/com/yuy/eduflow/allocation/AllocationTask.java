package com.yuy.eduflow.allocation;

import com.yuy.eduflow.teachingtask.TeachingTask;
import java.time.LocalDateTime;
import java.util.List;
import lombok.Data;

@Data
public class AllocationTask {
	private Long id;
	private String name;
	private String description;
	private Integer startWeek;
	private Integer endWeek;
	private String status;
	private String createdBy;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	// 非数据库字段
	private List<TeachingTask> teachingTasks;
}
