package com.yuy.eduflow.timeslot;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class TimeSlotService {
	private final TimeSlotMapper timeSlotMapper;

	public TimeSlotService(TimeSlotMapper timeSlotMapper) {
		this.timeSlotMapper = timeSlotMapper;
	}

	public List<TimeSlot> findAll(Integer weekNumber, Integer dayOfWeek) {
		return timeSlotMapper.findAll(weekNumber, dayOfWeek);
	}

	public TimeSlot findById(Long id) {
		TimeSlot timeSlot = timeSlotMapper.findById(id);
		if (timeSlot == null) {
			throw new IllegalArgumentException("时间段不存在");
		}
		return timeSlot;
	}

	public TimeSlot create(TimeSlotRequest request) {
		TimeSlot timeSlot = toTimeSlot(new TimeSlot(), request);
		timeSlotMapper.insert(timeSlot);
		return findById(timeSlot.getId());
	}

	public TimeSlot update(Long id, TimeSlotRequest request) {
		findById(id);
		TimeSlot timeSlot = toTimeSlot(new TimeSlot(), request);
		timeSlot.setId(id);
		timeSlotMapper.update(timeSlot);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		timeSlotMapper.delete(id);
	}

	private TimeSlot toTimeSlot(TimeSlot timeSlot, TimeSlotRequest request) {
		if (request.weekNumber() == null) {
			throw new IllegalArgumentException("周次不能为空");
		}
		if (request.weekNumber() < 1) {
			throw new IllegalArgumentException("周次必须大于0");
		}
		if (request.weekNumber() > 18) {
			throw new IllegalArgumentException("周次必须在1到18之间");
		}
		if (request.dayOfWeek() == null) {
			throw new IllegalArgumentException("星期不能为空");
		}
		if (request.dayOfWeek() < 1 || request.dayOfWeek() > 7) {
			throw new IllegalArgumentException("星期必须在1到7之间");
		}
		if (request.periodIndex() == null) {
			throw new IllegalArgumentException("节次不能为空");
		}
		if (request.periodIndex() < 1) {
			throw new IllegalArgumentException("节次必须大于0");
		}
		if (request.periodIndex() > 6) {
			throw new IllegalArgumentException("节次必须在1到6之间");
		}
		if (!StringUtils.hasText(request.label())) {
			throw new IllegalArgumentException("时间段标签不能为空");
		}
		timeSlot.setWeekNumber(request.weekNumber());
		timeSlot.setDayOfWeek(request.dayOfWeek());
		timeSlot.setPeriodIndex(request.periodIndex());
		timeSlot.setLabel(request.label().trim());
		return timeSlot;
	}
}
