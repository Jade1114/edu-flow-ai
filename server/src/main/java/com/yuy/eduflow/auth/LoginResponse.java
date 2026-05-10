package com.yuy.eduflow.auth;

public record LoginResponse(
	Long id,
	String employeeNo,
	String name,
	String displayName,
	String role,
	Long teacherId,
	String department,
	String title
) {
}
