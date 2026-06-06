package com.yuy.eduflow.timeslot;

import java.time.LocalDateTime;
import lombok.Data;

@Data
public class TimeSlot {
	private Long id;
	private Integer weekNumber;
	private Integer dayOfWeek;
	private Integer periodIndex;
	private String label;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
}
