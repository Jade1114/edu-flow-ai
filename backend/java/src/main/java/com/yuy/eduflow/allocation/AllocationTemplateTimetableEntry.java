package com.yuy.eduflow.allocation;

import lombok.Data;

@Data
public class AllocationTemplateTimetableEntry {
	private Integer weekNumber;
	private Long templateId;
	private String templateCode;
	private Long templateFragmentId;
	private String fragmentCode;
	private Long teachingTaskId;
	private String sourceKey;
	private Long courseId;
	private String courseName;
	private Long teacherId;
	private String teacherName;
	private Long classGroupId;
	private String className;
	private Long classroomId;
	private String classroomName;
	private Integer dayOfWeek;
	private Integer periodIndex;
	private String requiredRoomType;
	private String sourceType;
}
