package com.yuy.eduflow.enums;

/**
 * TaskStatus 的 MyBatis TypeHandler。
 */
public class TaskStatusTypeHandler extends CodeEnumTypeHandler<TaskStatus> {
	public TaskStatusTypeHandler() {
		super(TaskStatus.class);
	}
}
