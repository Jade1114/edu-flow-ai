package com.yuy.eduflow.classgroup;

public record ClassGroupRequest(
	String name,
	String major,
	String department,
	String grade,
	Integer studentCount
) {
}
