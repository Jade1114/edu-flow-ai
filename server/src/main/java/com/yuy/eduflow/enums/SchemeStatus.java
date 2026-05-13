package com.yuy.eduflow.enums;

/**
 * 分课方案状态。
 * 适用于：allocation_scheme（分课候选方案）。
 */
public enum SchemeStatus implements CodeEnum {
	CANDIDATE("CANDIDATE", "候选"),
	CONFIRMED("CONFIRMED", "已确认"),
	REJECTED("REJECTED", "已拒绝");

	private final String code;
	private final String label;

	SchemeStatus(String code, String label) {
		this.code = code;
		this.label = label;
	}

	public String code() {
		return code;
	}

	public String label() {
		return label;
	}

	public static SchemeStatus from(String code) {
		if (code == null || code.isBlank()) {
			return null;
		}
		for (SchemeStatus status : values()) {
			if (status.code.equalsIgnoreCase(code.trim())) {
				return status;
			}
		}
		throw new IllegalArgumentException("未知分课方案状态: " + code);
	}
}
