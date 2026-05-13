package com.yuy.eduflow.teacher;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class TeacherProfile {
	private Long id;
	private Long teacherId;
    private String availableTimeText;
	private String unavailableTimeText;
	private String workloadRequirement;
	private String specialNote;
	private String vectorText;
	private Boolean vectorIndexed;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
