package com.yuy.eduflow.classgroup;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class ClassGroup {
	private Long id;
	private String name;
	private String major;
	private String department;
	private String grade;
	private Integer studentCount;
	private String description;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
