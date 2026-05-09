package com.yuy.eduflow.classgroup;

public record ClassGroupRequest(
	String name,
	String major,
	String grade,
	Integer studentCount,
	String description
) {
}
