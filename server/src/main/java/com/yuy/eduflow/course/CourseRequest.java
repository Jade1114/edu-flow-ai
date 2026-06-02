package com.yuy.eduflow.course;

public record CourseRequest(
	String name,
	String courseType,
	String requiredRoomType,
	Integer requiredHours,
	String description,
	String status
) {
}
