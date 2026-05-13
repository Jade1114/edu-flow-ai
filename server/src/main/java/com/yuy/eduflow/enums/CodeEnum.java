package com.yuy.eduflow.enums;

/**
 * 所有状态枚举的公共接口，支持通过 code 进行数据库字符串映射。
 */
public interface CodeEnum {
	String code();
	String label();
}
