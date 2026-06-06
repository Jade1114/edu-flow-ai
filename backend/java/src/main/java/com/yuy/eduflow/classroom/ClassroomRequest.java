package com.yuy.eduflow.classroom;

public record ClassroomRequest(
	String name,
	String building,
	Integer capacity,
	String classroomType,
	String status
) {
}
