package com.yuy.eduflow.ml;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class MlFeedbackEvent {
	private Long id;
	private String eventType;
	private Long taskId;
	private Long schemeId;
	private Long itemId;
	private Long teachingTaskId;
	private String actorType;
	private String actorId;
	private String reasonCode;
	private String reasonText;
	private String beforeSnapshotJson;
	private String afterSnapshotJson;
	private String contextSnapshotJson;
	private LocalDateTime createdAt;
}
