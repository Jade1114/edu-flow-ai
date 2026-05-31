package com.yuy.eduflow.course;

import com.yuy.eduflow.enums.ActiveStatus;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class Course {
	private Long id;
	private String name;
	private String code;
	private Double credits;
	private String courseType;
	private Integer requiredHours;
	private String description;
    private ActiveStatus status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
