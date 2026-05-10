package com.yuy.eduflow.adjustment;

import static org.assertj.core.api.Assertions.assertThat;

import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class AdjustmentSuggestionParseServiceTests {

	@Test
	void parsesFencedJsonCandidates() {
		AdjustmentSuggestionParseService service = new AdjustmentSuggestionParseService(
			new StubClassroomService(5L),
			new StubTimeSlotService(9L),
			new ObjectMapper()
		);

		AdjustmentSuggestionPreview preview = service.parse(1L, 2L, """
			模型输出如下：
			```json
			{
			  "candidates": [
			    {
			      "summary": "优先满足教师周三上午偏好",
			      "newTimeSlotId": "9",
			      "newClassroomId": 5
			    }
			  ]
			}
			```
			""");

		assertThat(preview.requestId()).isEqualTo(1L);
		assertThat(preview.assignmentId()).isEqualTo(2L);
		assertThat(preview.candidates()).containsExactly(new AdjustmentSuggestionCandidate(
			0,
			"优先满足教师周三上午偏好",
			9L,
			5L,
			true,
			null
		));
		assertThat(preview.validationMessages()).isEmpty();
	}

	private static class StubClassroomService extends ClassroomService {
		private final Long existingId;

		StubClassroomService(Long existingId) {
			super(null);
			this.existingId = existingId;
		}

		@Override
		public Classroom findById(Long id) {
			if (!existingId.equals(id)) {
				throw new IllegalArgumentException("教室不存在");
			}
			Classroom classroom = new Classroom();
			classroom.setId(id);
			return classroom;
		}
	}

	private static class StubTimeSlotService extends TimeSlotService {
		private final Long existingId;

		StubTimeSlotService(Long existingId) {
			super(null);
			this.existingId = existingId;
		}

		@Override
		public TimeSlot findById(Long id) {
			if (!existingId.equals(id)) {
				throw new IllegalArgumentException("时间段不存在");
			}
			TimeSlot timeSlot = new TimeSlot();
			timeSlot.setId(id);
			return timeSlot;
		}
	}
}
