package com.yuy.eduflow.enums;

import com.yuy.eduflow.common.exception.ValidationException;

/**
 * 课表安排状态。
 * 适用于：course_assignment（正式课表记录）。
 */
public enum AssignmentStatus implements CodeEnum {
	ACTIVE("ACTIVE", "生效中"),
	INACTIVE("INACTIVE", "已作废");

	private final String code;
	private final String label;

	AssignmentStatus(String code, String label) {
		this.code = code;
		this.label = label;
	}

	public String code() {
		return code;
	}

	public String label() {
		return label;
	}

	public static AssignmentStatus from(String code) {
		if (code == null || code.isBlank()) {
			return null;
		}
		for (AssignmentStatus status : values()) {
			if (status.code.equalsIgnoreCase(code.trim())) {
				return status;
			}
		}
		throw new ValidationException("未知课表安排状态: " + code);
	}
}
