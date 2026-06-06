package com.yuy.eduflow.teacher;

public record TeacherProfileRequest(
    String availabilityMatrixJson,
    String profileNote,
    String profilePreferenceJson
) {
}
