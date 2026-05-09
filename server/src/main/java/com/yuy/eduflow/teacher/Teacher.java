package com.yuy.eduflow.teacher;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class Teacher {
	private Long id;
	private String name;
	private String department;
	private String title;
	private Integer maxWeeklyHours;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
