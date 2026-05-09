package com.yuy.eduflow.teacher;

public record TeacherProfileRequest(
	String skillText,
	String availableTimeText,
	String unavailableTimeText,
	String workloadRequirement,
	String specialNote
) {
}
