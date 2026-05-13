package com.yuy.eduflow.enums;

/**
 * 分课任务状态。
 * 适用于：allocation_task（分课任务）。
 */
public enum TaskStatus implements CodeEnum {
	DRAFT("DRAFT", "草稿"),
	PENDING("PENDING", "待处理"),
	CONFIRMED("CONFIRMED", "已确认"),
	REJECTED("REJECTED", "已拒绝");

	private final String code;
	private final String label;

	TaskStatus(String code, String label) {
		this.code = code;
		this.label = label;
	}

	public String code() {
		return code;
	}

	public String label() {
		return label;
	}

	public static TaskStatus from(String code) {
		if (code == null || code.isBlank()) {
			return null;
		}
		for (TaskStatus status : values()) {
			if (status.code.equalsIgnoreCase(code.trim())) {
				return status;
			}
		}
		throw new IllegalArgumentException("未知分课任务状态: " + code);
	}
}
