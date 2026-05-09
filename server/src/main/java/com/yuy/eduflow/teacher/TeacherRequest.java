package com.yuy.eduflow.teacher;

public record TeacherRequest(
	String name,
	String department,
	String title,
	Integer maxWeeklyHours,
	String status
) {
}
