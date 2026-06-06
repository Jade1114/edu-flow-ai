package com.yuy.eduflow.teacher;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class TeacherProfile {
	private Long id;
	private Long teacherId;
    private String availabilityMatrixJson;
    private String profileNote;
    private String profilePreferenceJson;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
