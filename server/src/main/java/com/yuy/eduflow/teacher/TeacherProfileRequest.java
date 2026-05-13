package com.yuy.eduflow.teacher;

public record TeacherProfileRequest(
    String availableTimeText,
    String unavailableTimeText,
    String workloadRequirement,
    String specialNote
) {
}
