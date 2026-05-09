package com.yuy.eduflow.course;

public record CourseRequest(
	String name,
	String courseType,
	Integer requiredHours,
	String requiredSkill,
	String description,
	String status
) {
}
