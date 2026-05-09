package com.yuy.eduflow.timeslot;

public record TimeSlotRequest(
	Integer weekNumber,
	Integer dayOfWeek,
	Integer periodIndex,
	String label
) {
}
