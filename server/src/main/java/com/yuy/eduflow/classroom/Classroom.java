package com.yuy.eduflow.classroom;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class Classroom {
	private Long id;
	private String name;
	private String building;
	private Integer capacity;
	private String classroomType;
	private String status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
