package com.yuy.eduflow.teacher;

public record TeacherProfileParseRequest(
    String availabilityMatrixJson,
    String profileNote
) {
}
