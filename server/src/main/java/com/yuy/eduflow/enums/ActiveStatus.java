package com.yuy.eduflow.enums;

/**
 * 基础实体活跃状态。
 * 适用于：教师、课程、教室、教学任务、教师画像等基础实体。
 */
public enum ActiveStatus implements CodeEnum {
	ACTIVE("ACTIVE", "活跃"),
	INACTIVE("INACTIVE", "停用");

	private final String code;
	private final String label;

	ActiveStatus(String code, String label) {
		this.code = code;
		this.label = label;
	}

	public String code() {
		return code;
	}

	public String label() {
		return label;
	}

	public static ActiveStatus from(String code) {
		if (code == null || code.isBlank()) {
			return null;
		}
		for (ActiveStatus status : values()) {
			if (status.code.equalsIgnoreCase(code.trim())) {
				return status;
			}
		}
		throw new IllegalArgumentException("未知活跃状态: " + code);
	}
}
