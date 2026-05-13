package com.yuy.eduflow.course;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class Course {
	private Long id;
	private String name;
	private String courseType;
	private Integer requiredHours;
	private String description;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
