package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.allocation.AllocationRagTeacherResult;
import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import com.yuy.eduflow.assignment.CourseAssignmentView;
import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classgroup.ClassGroupService;
import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.course.CourseService;
import com.yuy.eduflow.rag.TeacherProfileVectorService;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherService;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AdjustmentSuggestionPromptBuilderService {
	private static final String ACTIVE_STATUS = "ACTIVE";
	private static final String SUBMITTED_STATUS = "SUBMITTED";
	private static final int DEFAULT_TOP_K = 5;
	private static final int CLASSROOM_LIST_LIMIT = 40;
	private static final int TIME_SLOT_LIST_LIMIT = 80;
	private static final int SCHEDULE_LIST_LIMIT = 80;
	private static final int TEACHER_PROFILE_TEXT_LIMIT = 260;
	private static final int TEXT_FIELD_LIMIT = 220;

	private final AdjustmentRequestService adjustmentRequestService;
	private final CourseAssignmentService courseAssignmentService;
	private final CourseAssignmentMapper courseAssignmentMapper;
	private final CourseService courseService;
	private final ClassGroupService classGroupService;
	private final TeacherService teacherService;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;
	private final TeacherProfileVectorService teacherProfileVectorService;

	public AdjustmentSuggestionPromptBuilderService(
		AdjustmentRequestService adjustmentRequestService,
		CourseAssignmentService courseAssignmentService,
		CourseAssignmentMapper courseAssignmentMapper,
		CourseService courseService,
		ClassGroupService classGroupService,
		TeacherService teacherService,
		ClassroomService classroomService,
		TimeSlotService timeSlotService,
		TeacherProfileVectorService teacherProfileVectorService
	) {
		this.adjustmentRequestService = adjustmentRequestService;
		this.courseAssignmentService = courseAssignmentService;
		this.courseAssignmentMapper = courseAssignmentMapper;
		this.courseService = courseService;
		this.classGroupService = classGroupService;
		this.teacherService = teacherService;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
		this.teacherProfileVectorService = teacherProfileVectorService;
	}

	public AdjustmentSuggestionPromptPreview buildPreview(Long requestId, Integer topK) {
		AdjustmentRequest request = adjustmentRequestService.findById(requestId);
		if (!SUBMITTED_STATUS.equals(request.getStatus())) {
			throw new IllegalArgumentException("只有 SUBMITTED 状态的调课申请可以生成候选方案");
		}
		CourseAssignment assignment = courseAssignmentService.findById(request.getAssignmentId());
		validateRequestMatchesAssignment(request, assignment);

		Course course = courseService.findById(assignment.getCourseId());
		ClassGroup classGroup = classGroupService.findById(assignment.getClassGroupId());
		Teacher teacher = teacherService.findById(assignment.getTeacherId());
		Classroom originalClassroom = classroomService.findById(assignment.getClassroomId());
		TimeSlot originalTimeSlot = timeSlotService.findById(assignment.getTimeSlotId());
		List<Classroom> classrooms = classroomService.findAll(null, ACTIVE_STATUS);
		List<TimeSlot> timeSlots = timeSlotService.findAll(null, null);
		List<CourseAssignmentView> activeSchedule = courseAssignmentMapper.findViews(
			null,
			null,
			null,
			null,
			null,
			ACTIVE_STATUS
		);
		String ragQuery = buildRagQuery(request, course, classGroup, teacher, originalTimeSlot, originalClassroom);
		List<AllocationRagTeacherResult> ragTeachers = teacherProfileVectorService.search(
				ragQuery,
				topK == null ? DEFAULT_TOP_K : topK,
				ACTIVE_STATUS
			)
			.stream()
			.map(AllocationRagTeacherResult::from)
			.toList();
		String outputSchema = buildOutputSchema();
		return new AdjustmentSuggestionPromptPreview(
			request.getId(),
			assignment.getId(),
			buildSystemPrompt(),
			buildUserPrompt(
				request,
				assignment,
				course,
				classGroup,
				teacher,
				originalClassroom,
				originalTimeSlot,
				classrooms,
				timeSlots,
				activeSchedule,
				ragQuery,
				ragTeachers,
				outputSchema
			),
			outputSchema
		);
	}

	private void validateRequestMatchesAssignment(AdjustmentRequest request, CourseAssignment assignment) {
		if (!request.getTeacherId().equals(assignment.getTeacherId())) {
			throw new IllegalArgumentException("调课申请教师与原课程安排教师不一致");
		}
		if (!ACTIVE_STATUS.equals(assignment.getStatus())) {
			throw new IllegalArgumentException("原课程安排不是 ACTIVE 状态，不能生成调课候选方案");
		}
	}

	private String buildSystemPrompt() {
		return """
			你是高校教务调课助手，负责根据后端提供的结构化数据和教师画像生成候选调课方案。
			你只能使用输入中明确给出的 ID：newTimeSlotId、newClassroomId。
			不得编造教室或时间段；不得改变课程、班级或教师。
			你必须只输出合法 JSON，不输出 Markdown、解释文字或代码块。
			你不负责最终合法性判定；后端会继续执行确定性的正式课表冲突检测。
			""".trim();
	}

	private String buildUserPrompt(
		AdjustmentRequest request,
		CourseAssignment assignment,
		Course course,
		ClassGroup classGroup,
		Teacher teacher,
		Classroom originalClassroom,
		TimeSlot originalTimeSlot,
		List<Classroom> classrooms,
		List<TimeSlot> timeSlots,
		List<CourseAssignmentView> activeSchedule,
		String ragQuery,
		List<AllocationRagTeacherResult> ragTeachers,
		String outputSchema
	) {
		StringBuilder prompt = new StringBuilder();
		appendLine(prompt, "请为以下高校调课申请生成候选调课方案。");
		appendLine(prompt, "");
		appendLine(prompt, "## 调课申请");
		appendLine(prompt, "requestId: " + request.getId());
		appendLine(prompt, "assignmentId: " + assignment.getId());
		appendLine(prompt, "reason: " + valueOrDefault(request.getReason(), "未提供"));
		appendLine(prompt, "preferredTimeText: " + valueOrDefault(request.getPreferredTimeText(), "未提供"));
		appendLine(prompt, "preferredTimeSlotId: " + valueOrDefault(request.getPreferredTimeSlotId(), "未提供"));
		appendLine(prompt, "preferredClassroomId: " + valueOrDefault(request.getPreferredClassroomId(), "未提供"));
		appendLine(prompt, "");
		appendLine(prompt, "## 原课程安排");
		appendLine(prompt, "course: " + formatCourse(course));
		appendLine(prompt, "classGroup: " + formatClassGroup(classGroup));
		appendLine(prompt, "teacher: " + formatTeacher(teacher));
		appendLine(prompt, "originalTimeSlot: " + formatTimeSlot(originalTimeSlot));
		appendLine(prompt, "originalClassroom: " + formatClassroom(originalClassroom));
		appendLine(prompt, "");
		appendLine(prompt, "## 当前正式课表（ACTIVE，共 " + activeSchedule.size() + " 条，以下为摘要）");
		appendLine(prompt, summarize(activeSchedule, SCHEDULE_LIST_LIMIT, this::formatAssignmentView));
		appendLine(prompt, "");
		appendLine(prompt, "## 可选教室（ACTIVE，共 " + classrooms.size() + " 间）");
		appendLine(prompt, summarize(classrooms, CLASSROOM_LIST_LIMIT, this::formatClassroom));
		appendLine(prompt, "");
		appendLine(prompt, "## 可选时间段（共 " + timeSlots.size() + " 个）");
		appendLine(prompt, summarize(timeSlots, TIME_SLOT_LIST_LIMIT, this::formatTimeSlot));
		appendLine(prompt, "");
		appendLine(prompt, "## RAG 检索到的教师画像（topK=" + ragTeachers.size() + "）");
		appendLine(prompt, "ragQuery: " + ragQuery);
		appendLine(prompt, summarize(ragTeachers, ragTeachers.size(), this::formatTeacherProfile));
		appendLine(prompt, "");
		appendLine(prompt, "## 固定规则");
		appendLine(prompt, "1. 只调整 assignmentId=" + assignment.getId() + " 的时间段和教室。");
		appendLine(prompt, "2. 不要改变 courseId=" + assignment.getCourseId() + "、classGroupId=" + assignment.getClassGroupId() + "、teacherId=" + assignment.getTeacherId() + "。");
		appendLine(prompt, "3. 只允许使用上文列出的 timeSlotId 作为 newTimeSlotId，使用 classroomId 作为 newClassroomId。");
		appendLine(prompt, "4. 优先满足调课原因和调课倾向，尤其是 preferredTimeText / preferredTimeSlotId / preferredClassroomId。");
		appendLine(prompt, "5. 尽量避开教师画像中的不可用时间，优先匹配可用时间。");
		appendLine(prompt, "6. 尽量避免教师、班级、教室在同一 timeSlotId 的正式课表冲突；最终以后端冲突检测为准。");
		appendLine(prompt, "7. 输出 2 到 5 个候选；如果信息不足，可以减少候选数量并在 summary 中说明原因。");
		appendLine(prompt, "");
		appendLine(prompt, "## 输出要求");
		appendLine(prompt, "只输出 JSON，业务输出必须符合以下 JSON Schema；候选项不得包含 schema 未列字段：");
		appendLine(prompt, outputSchema);
		return prompt.toString().trim();
	}

	private String buildRagQuery(
		AdjustmentRequest request,
		Course course,
		ClassGroup classGroup,
		Teacher teacher,
		TimeSlot originalTimeSlot,
		Classroom originalClassroom
	) {
		StringBuilder query = new StringBuilder();
		appendLine(query, "任务类型：MVP 调课候选方案教师画像检索。");
		appendLine(query, "申请教师：" + teacher.getName() + optionalPart("院系", teacher.getDepartment()) + optionalPart("职称", teacher.getTitle()));
		appendLine(query, "课程：" + course.getName() + optionalPart("课程类型", course.getCourseType()) + optionalPart("能力要求", course.getRequiredSkill()));
		appendLine(query, "班级：" + classGroup.getName() + optionalPart("专业", classGroup.getMajor()) + optionalPart("年级", classGroup.getGrade()));
		appendLine(query, "原时间：" + formatTimeSlot(originalTimeSlot));
		appendLine(query, "原教室：" + formatClassroom(originalClassroom));
		appendLine(query, "调课原因：" + valueOrDefault(request.getReason(), "未提供"));
		appendLine(query, "调课倾向：" + valueOrDefault(request.getPreferredTimeText(), "未提供"));
		appendLine(query, "检索目标说明：检索该教师和相近教师画像中关于可用时间、不可用时间、工作量要求和特殊说明的信息，用于生成调课候选方案。");
		return query.toString().trim();
	}

	private String buildOutputSchema() {
		return """
			{
			  "type": "object",
			  "required": ["candidates"],
			  "additionalProperties": false,
			  "properties": {
			    "candidates": {
			      "type": "array",
			      "items": {
			        "type": "object",
			        "required": ["summary", "newTimeSlotId", "newClassroomId"],
			        "additionalProperties": false,
			        "properties": {
			          "summary": { "type": "string" },
			          "newTimeSlotId": { "type": "integer" },
			          "newClassroomId": { "type": "integer" }
			        }
			      }
			    }
			  }
			}
			""".trim();
	}

	private void appendLine(StringBuilder builder, String value) {
		builder.append(value).append('\n');
	}

	private <T> String summarize(List<T> values, int limit, Function<T, String> formatter) {
		if (values.isEmpty()) {
			return "无";
		}
		String summary = values.stream()
			.limit(limit)
			.map(formatter)
			.collect(Collectors.joining("\n"));
		if (values.size() > limit) {
			summary = summary + "\n另有 " + (values.size() - limit) + " 项未展开";
		}
		return summary;
	}

	private String formatCourse(Course course) {
		return "courseId=" + course.getId()
			+ ", name=" + course.getName()
			+ optionalPart("courseType", course.getCourseType())
			+ optionalPart("requiredHours", course.getRequiredHours())
			+ optionalPart("requiredSkill", course.getRequiredSkill())
			+ optionalPart("description", course.getDescription());
	}

	private String formatClassGroup(ClassGroup classGroup) {
		return "classGroupId=" + classGroup.getId()
			+ ", name=" + classGroup.getName()
			+ optionalPart("major", classGroup.getMajor())
			+ optionalPart("grade", classGroup.getGrade())
			+ optionalPart("studentCount", classGroup.getStudentCount())
			+ optionalPart("description", classGroup.getDescription());
	}

	private String formatTeacher(Teacher teacher) {
		return "teacherId=" + teacher.getId()
			+ ", name=" + teacher.getName()
			+ optionalPart("department", teacher.getDepartment())
			+ optionalPart("title", teacher.getTitle())
			+ optionalPart("maxWeeklyHours", teacher.getMaxWeeklyHours());
	}

	private String formatClassroom(Classroom classroom) {
		return "- classroomId=" + classroom.getId()
			+ ", name=" + classroom.getName()
			+ optionalPart("building", classroom.getBuilding())
			+ optionalPart("capacity", classroom.getCapacity())
			+ optionalPart("classroomType", classroom.getClassroomType());
	}

	private String formatTimeSlot(TimeSlot timeSlot) {
		return "- timeSlotId=" + timeSlot.getId()
			+ ", weekNumber=" + timeSlot.getWeekNumber()
			+ ", dayOfWeek=" + timeSlot.getDayOfWeek()
			+ ", periodIndex=" + timeSlot.getPeriodIndex()
			+ optionalPart("label", timeSlot.getLabel());
	}

	private String formatAssignmentView(CourseAssignmentView view) {
		return "- assignmentId=" + view.getId()
			+ ", course=" + view.getCourseName() + "(" + view.getCourseId() + ")"
			+ ", classGroup=" + view.getClassGroupName() + "(" + view.getClassGroupId() + ")"
			+ ", teacher=" + view.getTeacherName() + "(" + view.getTeacherId() + ")"
			+ ", classroom=" + view.getClassroomName() + "(" + view.getClassroomId() + ")"
			+ ", timeSlotId=" + view.getTimeSlotId()
			+ optionalPart("timeSlotLabel", view.getTimeSlotLabel());
	}

	private String formatTeacherProfile(AllocationRagTeacherResult teacher) {
		return "- teacherId=" + teacher.teacherId()
			+ ", profileId=" + teacher.profileId()
			+ optionalPart("teacherName", teacher.teacherName())
			+ optionalPart("department", teacher.department())
			+ optionalPart("title", teacher.title())
			+ optionalPart("score", teacher.score())
			+ optionalPart("vectorText", truncate(teacher.vectorText(), TEACHER_PROFILE_TEXT_LIMIT));
	}

	private String optionalPart(String label, Object value) {
		if (value == null) {
			return "";
		}
		String text = value instanceof String stringValue
			? truncate(stringValue, TEXT_FIELD_LIMIT)
			: String.valueOf(value).trim();
		return StringUtils.hasText(text) ? ", " + label + "=" + text : "";
	}

	private String valueOrDefault(Object value, String defaultValue) {
		if (value == null) {
			return defaultValue;
		}
		if (value instanceof String stringValue) {
			return StringUtils.hasText(stringValue) ? stringValue.trim() : defaultValue;
		}
		return String.valueOf(value);
	}

	private String truncate(String value, int limit) {
		if (!StringUtils.hasText(value)) {
			return null;
		}
		String text = value.trim();
		if (text.length() <= limit) {
			return text;
		}
		return text.substring(0, limit) + "...";
	}
}
