package com.yuy.eduflow.allocation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classgroup.ClassGroupService;
import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.course.CourseService;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherService;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class AllocationGenerateParseServiceTests {

	@Test
	void parsesFencedJsonAndReturnsValidationMessages() {
		AllocationGenerateParseService service = serviceWithRawResponse("""
			模型输出如下：
			```json
			{
			  "schemes": [
			    {
			      "schemeName": "方案一",
			      "summary": "优先匹配教师能力",
			      "score": 101,
			      "satisfiedSummary": "基本满足",
			      "items": [
			        {
			          "courseId": 1,
			          "classGroupId": 1,
			          "teacherId": 1,
			          "classroomId": 1,
			          "timeSlotId": 1
			        }
			      ]
			    }
			  ]
			}
			```
			""", 1L, 1L, 1L, 1L, 1L);

		AllocationParsePreview preview = service.generateParsePreview(1L, 5);

		assertThat(preview.taskId()).isEqualTo(1L);
		assertThat(preview.taskName()).isEqualTo("测试分课任务");
		assertThat(preview.schemes()).hasSize(1);
		assertThat(preview.schemes().getFirst().schemeName()).isEqualTo("方案一");
		assertThat(preview.schemes().getFirst().items()).containsExactly(
			new AllocationParsedItem(1L, 1L, 1L, 1L, 1L)
		);
		assertThat(preview.validationMessages()).containsExactly("第 1 个方案 score=101 超出建议范围 0-100");
	}

	@Test
	void rejectsMissingSchemesArray() {
		AllocationGenerateParseService service = serviceWithRawResponse("{}", 1L, 1L, 1L, 1L, 1L);

		assertThatThrownBy(() -> service.generateParsePreview(1L, 5))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("AI 输出顶层必须包含 schemes 数组");
	}

	@Test
	void rejectsUnknownReferencedId() {
		AllocationGenerateParseService service = serviceWithRawResponse("""
			{
			  "schemes": [
			    {
			      "schemeName": "方案一",
			      "items": [
			        {
			          "courseId": 99,
			          "classGroupId": 1,
			          "teacherId": 1,
			          "classroomId": 1,
			          "timeSlotId": 1
			        }
			      ]
			    }
			  ]
			}
			""", 1L, 1L, 1L, 1L, 1L);

		assertThatThrownBy(() -> service.generateParsePreview(1L, 5))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("第 1 个方案第 1 个明细 courseId 不存在：99");
	}

	private AllocationGenerateParseService serviceWithRawResponse(
		String rawResponse,
		Long courseId,
		Long classGroupId,
		Long teacherId,
		Long classroomId,
		Long timeSlotId
	) {
		return new AllocationGenerateParseService(
			new StubGeneratePreviewService(rawResponse),
			new StubCourseService(courseId),
			new StubClassGroupService(classGroupId),
			new StubTeacherService(teacherId),
			new StubClassroomService(classroomId),
			new StubTimeSlotService(timeSlotId),
			new ObjectMapper()
		);
	}

	private static class StubGeneratePreviewService extends AllocationGeneratePreviewService {
		private final String rawResponse;

		StubGeneratePreviewService(String rawResponse) {
			super(null, null);
			this.rawResponse = rawResponse;
		}

		@Override
		public AllocationGeneratePreview generate(Long taskId, Integer topK) {
			return new AllocationGeneratePreview(
				taskId,
				"测试分课任务",
				"system",
				"user",
				"schema",
				rawResponse
			);
		}
	}

	private static class StubCourseService extends CourseService {
		private final Long existingId;

		StubCourseService(Long existingId) {
			super(null);
			this.existingId = existingId;
		}

		@Override
		public Course findById(Long id) {
			if (!existingId.equals(id)) {
				throw new IllegalArgumentException("课程不存在");
			}
			Course course = new Course();
			course.setId(id);
			return course;
		}
	}

	private static class StubClassGroupService extends ClassGroupService {
		private final Long existingId;

		StubClassGroupService(Long existingId) {
			super(null);
			this.existingId = existingId;
		}

		@Override
		public ClassGroup findById(Long id) {
			if (!existingId.equals(id)) {
				throw new IllegalArgumentException("班级不存在");
			}
			ClassGroup classGroup = new ClassGroup();
			classGroup.setId(id);
			return classGroup;
		}
	}

	private static class StubTeacherService extends TeacherService {
		private final Long existingId;

		StubTeacherService(Long existingId) {
			super(null);
			this.existingId = existingId;
		}

		@Override
		public Teacher findById(Long id) {
			if (!existingId.equals(id)) {
				throw new IllegalArgumentException("教师不存在");
			}
			Teacher teacher = new Teacher();
			teacher.setId(id);
			return teacher;
		}
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
