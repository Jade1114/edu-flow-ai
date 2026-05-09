package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classgroup.ClassGroupService;
import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.course.CourseService;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationPromptBuilderService {
	private static final String ACTIVE_STATUS = "ACTIVE";
	private static final int COURSE_LIST_LIMIT = 30;
	private static final int CLASS_GROUP_LIST_LIMIT = 40;
	private static final int CLASSROOM_LIST_LIMIT = 20;
	private static final int TIME_SLOT_LIST_LIMIT = 30;
	private static final int TEACHER_PROFILE_TEXT_LIMIT = 220;
	private static final int TEXT_FIELD_LIMIT = 220;

	private final AllocationTaskService allocationTaskService;
	private final AllocationRagContextService allocationRagContextService;
	private final CourseService courseService;
	private final ClassGroupService classGroupService;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;

	public AllocationPromptBuilderService(
		AllocationTaskService allocationTaskService,
		AllocationRagContextService allocationRagContextService,
		CourseService courseService,
		ClassGroupService classGroupService,
		ClassroomService classroomService,
		TimeSlotService timeSlotService
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationRagContextService = allocationRagContextService;
		this.courseService = courseService;
		this.classGroupService = classGroupService;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
	}

	public AllocationPromptPreview buildPreview(Long taskId, Integer topK) {
		AllocationTask task = allocationTaskService.findById(taskId);
		AllocationRagContext ragContext = allocationRagContextService.buildContext(taskId, topK);
		List<Course> courses = courseService.findAll(null, ACTIVE_STATUS);
		List<ClassGroup> classGroups = classGroupService.findAll(null);
		List<Classroom> classrooms = classroomService.findAll(null, ACTIVE_STATUS);
		List<TimeSlot> timeSlots = timeSlotService.findAll(null, null);
		String outputSchema = buildOutputSchema();
		return new AllocationPromptPreview(
			task.getId(),
			task.getName(),
			buildSystemPrompt(),
			buildUserPrompt(task, courses, classGroups, classrooms, timeSlots, ragContext, outputSchema),
			outputSchema,
			ragContext
		);
	}

	private String buildSystemPrompt() {
		return """
			你是高校教务分课助手，负责根据后端提供的结构化数据和教师画像生成候选分课方案。
			你只能使用输入中明确给出的 ID：courseId、classGroupId、teacherId、classroomId、timeSlotId。
			不得编造课程、班级、教师、教室或时间段；不得输出未提供的 ID。
			你必须只输出合法 JSON，不输出 Markdown、解释文字或代码块。
			你需要尽量满足教师能力、可用时间、不可用时间、工作量、教室容量和分课优先规则。
			你不负责最终合法性判定；后端会继续执行确定性的冲突检测和落库校验。
			""".trim();
	}

	private String buildUserPrompt(
		AllocationTask task,
		List<Course> courses,
		List<ClassGroup> classGroups,
		List<Classroom> classrooms,
		List<TimeSlot> timeSlots,
		AllocationRagContext ragContext,
		String outputSchema
	) {
		StringBuilder prompt = new StringBuilder();
		appendLine(prompt, "请为以下高校分课任务生成候选分课方案。");
		appendLine(prompt, "");
		appendLine(prompt, "## 分课任务");
		appendLine(prompt, "taskId: " + task.getId());
		appendLine(prompt, "taskName: " + task.getName());
		appendLine(prompt, "description: " + valueOrDefault(task.getDescription(), "未提供"));
		appendLine(prompt, "priorityRule: " + valueOrDefault(task.getPriorityRule(), "优先匹配教师课程能力、可用时间、工作量约束与特殊说明。"));
		appendLine(prompt, "");
		appendLine(prompt, "## 课程列表（ACTIVE，共 " + courses.size() + " 门，以下为预览摘要）");
		appendLine(prompt, summarize(courses, COURSE_LIST_LIMIT, this::formatCourse));
		appendLine(prompt, "");
		appendLine(prompt, "## 班级列表（全部，共 " + classGroups.size() + " 个，以下为预览摘要）");
		appendLine(prompt, summarize(classGroups, CLASS_GROUP_LIST_LIMIT, this::formatClassGroup));
		appendLine(prompt, "");
		appendLine(prompt, "## 可用教室（ACTIVE，共 " + classrooms.size() + " 间，以下为预览摘要）");
		appendLine(prompt, summarize(classrooms, CLASSROOM_LIST_LIMIT, this::formatClassroom));
		appendLine(prompt, "");
		appendLine(prompt, "## 可用时间段（共 " + timeSlots.size() + " 个，以下为预览摘要）");
		appendLine(prompt, summarize(timeSlots, TIME_SLOT_LIST_LIMIT, this::formatTimeSlot));
		appendLine(prompt, "");
		appendLine(prompt, "## RAG 检索到的教师画像（topK=" + ragContext.topK() + "）");
		appendLine(prompt, "ragQuery: " + ragContext.query());
		appendLine(prompt, summarize(ragContext.teachers(), ragContext.teachers().size(), this::formatTeacherProfile));
		appendLine(prompt, "");
		appendLine(prompt, "## 固定规则");
		appendLine(prompt, "1. 只允许使用上文列出的 courseId、classGroupId、teacherId、classroomId、timeSlotId。");
		appendLine(prompt, "2. 每个 items 元素表示一个课程、班级、教师、教室和时间段的分配建议。");
		appendLine(prompt, "3. 优先匹配课程 requiredSkill 与教师画像中的 skillText / vectorText。");
		appendLine(prompt, "4. 尽量避开教师 unavailableTimeText，优先使用 availableTimeText 中匹配的时间。");
		appendLine(prompt, "5. 尽量让 classroom.capacity 覆盖 classGroup.studentCount，并匹配 classroomType 与 courseType。");
		appendLine(prompt, "6. 尽量避免同一教师、同一班级、同一教室在同一 timeSlotId 重复出现，但最终冲突检测以后端为准。");
		appendLine(prompt, "7. 如果信息不足，不要编造 ID；可以减少安排数量，并在 summary 或 satisfiedSummary 中说明原因。");
		appendLine(prompt, "");
		appendLine(prompt, "## 输出要求");
		appendLine(prompt, "只输出 JSON，业务输出必须符合以下 JSON Schema；items 中不得包含 schema 未列字段：");
		appendLine(prompt, outputSchema);
		return prompt.toString().trim();
	}

	private String buildOutputSchema() {
		return """
			{
			  "type": "object",
			  "required": ["schemes"],
			  "additionalProperties": false,
			  "properties": {
			    "schemes": {
			      "type": "array",
			      "items": {
			        "type": "object",
			        "required": ["schemeName", "summary", "score", "satisfiedSummary", "items"],
			        "additionalProperties": false,
			        "properties": {
			          "schemeName": { "type": "string" },
			          "summary": { "type": "string" },
			          "score": { "type": "integer", "minimum": 0, "maximum": 100 },
			          "satisfiedSummary": { "type": "string" },
			          "items": {
			            "type": "array",
			            "items": {
			              "type": "object",
			              "required": ["courseId", "classGroupId", "teacherId", "classroomId", "timeSlotId"],
			              "additionalProperties": false,
			              "properties": {
			                "courseId": { "type": "integer" },
			                "classGroupId": { "type": "integer" },
			                "teacherId": { "type": "integer" },
			                "classroomId": { "type": "integer" },
			                "timeSlotId": { "type": "integer" }
			              }
			            }
			          }
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
		return "- courseId=" + course.getId()
			+ ", name=" + course.getName()
			+ optionalPart("courseType", course.getCourseType())
			+ optionalPart("requiredHours", course.getRequiredHours())
			+ optionalPart("requiredSkill", course.getRequiredSkill())
			+ optionalPart("description", course.getDescription());
	}

	private String formatClassGroup(ClassGroup classGroup) {
		return "- classGroupId=" + classGroup.getId()
			+ ", name=" + classGroup.getName()
			+ optionalPart("major", classGroup.getMajor())
			+ optionalPart("grade", classGroup.getGrade())
			+ optionalPart("studentCount", classGroup.getStudentCount())
			+ optionalPart("description", classGroup.getDescription());
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

	private String valueOrDefault(String value, String defaultValue) {
		return StringUtils.hasText(value) ? value.trim() : defaultValue;
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
