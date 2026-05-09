package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.classgroup.ClassGroupService;
import com.yuy.eduflow.classroom.Classroom;
import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.course.CourseService;
import com.yuy.eduflow.rag.TeacherProfileVectorService;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationRagContextService {
	private static final String ACTIVE_STATUS = "ACTIVE";
	private static final int DEFAULT_TOP_K = 5;
	private static final int COURSE_LIST_LIMIT = 20;
	private static final int CLASS_GROUP_LIST_LIMIT = 30;
	private static final int SKILL_LIST_LIMIT = 20;
	private static final int RESOURCE_EXAMPLE_LIMIT = 8;

	private final AllocationTaskService allocationTaskService;
	private final CourseService courseService;
	private final ClassGroupService classGroupService;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;
	private final TeacherProfileVectorService teacherProfileVectorService;

	public AllocationRagContextService(
		AllocationTaskService allocationTaskService,
		CourseService courseService,
		ClassGroupService classGroupService,
		ClassroomService classroomService,
		TimeSlotService timeSlotService,
		TeacherProfileVectorService teacherProfileVectorService
	) {
		this.allocationTaskService = allocationTaskService;
		this.courseService = courseService;
		this.classGroupService = classGroupService;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
		this.teacherProfileVectorService = teacherProfileVectorService;
	}

	public AllocationRagContext buildContext(Long taskId, Integer topK) {
		AllocationTask task = allocationTaskService.findById(taskId);
		int limit = topK == null ? DEFAULT_TOP_K : topK;
		List<Course> courses = courseService.findAll(null, ACTIVE_STATUS);
		List<ClassGroup> classGroups = classGroupService.findAll(null);
		List<Classroom> classrooms = classroomService.findAll(null, ACTIVE_STATUS);
		List<TimeSlot> timeSlots = timeSlotService.findAll(null, null);
		String query = buildQuery(task, courses, classGroups, classrooms, timeSlots);
		List<AllocationRagTeacherResult> teachers = teacherProfileVectorService.search(query, limit, ACTIVE_STATUS).stream()
			.map(AllocationRagTeacherResult::from)
			.toList();
		return new AllocationRagContext(task.getId(), task.getName(), query, limit, teachers);
	}

	private String buildQuery(
		AllocationTask task,
		List<Course> courses,
		List<ClassGroup> classGroups,
		List<Classroom> classrooms,
		List<TimeSlot> timeSlots
	) {
		StringBuilder query = new StringBuilder();
		appendLine(query, "任务类型：MVP 分课任务教师画像检索。");
		appendLine(query, "任务名称：" + task.getName());
		appendLine(query, "任务说明：" + valueOrDefault(task.getDescription(), "未提供"));
		appendLine(query, "课程列表（ACTIVE，共 " + courses.size() + " 门）：" + summarize(courses, COURSE_LIST_LIMIT, this::formatCourse));
		appendLine(query, "班级列表（全部，共 " + classGroups.size() + " 个）：" + summarize(classGroups, CLASS_GROUP_LIST_LIMIT, this::formatClassGroup));
		appendLine(query, "课程能力要求：" + summarizeCourseSkills(courses));
		appendLine(query, "分课优先规则：" + valueOrDefault(task.getPriorityRule(), "优先匹配教师课程能力、可用时间、工作量约束与特殊说明。"));
		appendLine(query, "教室资源摘要：ACTIVE 教室共 " + classrooms.size() + " 间，示例：" + summarize(classrooms, RESOURCE_EXAMPLE_LIMIT, this::formatClassroom));
		appendLine(query, "时间段摘要：可用时间段共 " + timeSlots.size() + " 个，示例：" + summarize(timeSlots, RESOURCE_EXAMPLE_LIMIT, this::formatTimeSlot));
		appendLine(query, "检索目标说明：从 ACTIVE 教师画像中检索最适合承担上述课程与班级分配的教师，重点关注课程技能、过往经验、可用/不可用时间、工作量要求和特殊约束。");
		return query.toString().trim();
	}

	private void appendLine(StringBuilder builder, String value) {
		builder.append(value).append('\n');
	}

	private String summarizeCourseSkills(List<Course> courses) {
		if (courses.isEmpty()) {
			return "未配置 ACTIVE 课程。";
		}
		String summary = courses.stream()
			.limit(SKILL_LIST_LIMIT)
			.map(course -> course.getName() + "：" + valueOrDefault(course.getRequiredSkill(), "未配置明确能力要求"))
			.collect(Collectors.joining("；"));
		if (courses.size() > SKILL_LIST_LIMIT) {
			summary = summary + "；另有 " + (courses.size() - SKILL_LIST_LIMIT) + " 门课程未展开";
		}
		return summary;
	}

	private <T> String summarize(List<T> values, int limit, Function<T, String> formatter) {
		if (values.isEmpty()) {
			return "无";
		}
		String summary = values.stream()
			.limit(limit)
			.map(formatter)
			.collect(Collectors.joining("；"));
		if (values.size() > limit) {
			summary = summary + "；另有 " + (values.size() - limit) + " 项未展开";
		}
		return summary;
	}

	private String formatCourse(Course course) {
		return course.getName()
			+ optionalPart("类型", course.getCourseType())
			+ optionalPart("课时", course.getRequiredHours());
	}

	private String formatClassGroup(ClassGroup classGroup) {
		return classGroup.getName()
			+ optionalPart("专业", classGroup.getMajor())
			+ optionalPart("年级", classGroup.getGrade())
			+ optionalPart("人数", classGroup.getStudentCount());
	}

	private String formatClassroom(Classroom classroom) {
		return classroom.getName()
			+ optionalPart("楼宇", classroom.getBuilding())
			+ optionalPart("容量", classroom.getCapacity())
			+ optionalPart("类型", classroom.getClassroomType());
	}

	private String formatTimeSlot(TimeSlot timeSlot) {
		return "第" + timeSlot.getWeekNumber() + "周 周" + timeSlot.getDayOfWeek()
			+ " 第" + timeSlot.getPeriodIndex() + "节 " + timeSlot.getLabel();
	}

	private String optionalPart(String label, Object value) {
		if (value == null) {
			return "";
		}
		String text = String.valueOf(value).trim();
		return StringUtils.hasText(text) ? "（" + label + "：" + text + "）" : "";
	}

	private String valueOrDefault(String value, String defaultValue) {
		return StringUtils.hasText(value) ? value.trim() : defaultValue;
	}
}
