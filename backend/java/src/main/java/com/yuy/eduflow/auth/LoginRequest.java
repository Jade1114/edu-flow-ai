package com.yuy.eduflow.auth;

public record LoginRequest(
	String employeeNo,
	String username,
	String password
) {
}
