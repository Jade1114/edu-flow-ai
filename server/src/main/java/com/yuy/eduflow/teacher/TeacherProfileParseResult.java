package com.yuy.eduflow.teacher;

import java.util.Map;

public record TeacherProfileParseResult(
    String profilePreferenceJson,
    Map<String, Object> parsedPreference,
    String interpretation
) {
}
