package com.yuy.eduflow.allocation;

import lombok.Data;

/**
 * 分课方案明细视图，展开教学任务、教室、时间段信息。
 */
@Data
public class AllocationItemView {
	private Long id;
	private Long schemeId;
	private Long teachingTaskId;
	private String courseName;
	private String teacherName;
	private String classGroupName;
	private Long classroomId;
	private String classroomName;
	private Long timeSlotId;
	private String timeSlotLabel;
	private Integer weekNumber;
	private Integer dayOfWeek;
	private Integer periodIndex;
	private Boolean valid;
	private String conflictMessage;
}
