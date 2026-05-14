package com.yuy.eduflow.teacher;

import com.yuy.eduflow.enums.ActiveStatus;
import java.time.LocalDateTime;
import lombok.Data;

@Data
public class Teacher {
	private Long id;
	private String employeeNo;
	private String password;
	private String role;
	private String name;
	private String department;
	private String title;
	private Integer maxWeeklyHours;
    private ActiveStatus status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
