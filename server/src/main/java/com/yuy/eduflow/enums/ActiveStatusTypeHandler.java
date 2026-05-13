package com.yuy.eduflow.enums;

/**
 * ActiveStatus 的 MyBatis TypeHandler。
 */
public class ActiveStatusTypeHandler extends CodeEnumTypeHandler<ActiveStatus> {
	public ActiveStatusTypeHandler() {
		super(ActiveStatus.class);
	}
}
