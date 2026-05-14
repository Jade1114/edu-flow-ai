package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.teachingtask.TeachingTask;
import com.yuy.eduflow.timeslot.TimeSlot;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Slf4j
@Service
public class AllocationPromptBuilderService {
	
	private static final int TIME_SLOT_LIST_LIMIT = 30;
	private static final int TEACHER_PROFILE_TEXT_LIMIT = 220;
	private static final int TEXT_FIELD_LIMIT = 220;

	private final AllocationTaskService allocationTaskService;
	private final AllocationRagContextService allocationRagContextService;
	private final TimeSlotService timeSlotService;

	public AllocationPromptBuilderService(
		AllocationTaskService allocationTaskService,
		AllocationRagContextService allocationRagContextService,
		TimeSlotService timeSlotService
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationRagContextService = allocationRagContextService;
		this.timeSlotService = timeSlotService;
	}

	private static String readResource(String path) {
		try {
			InputStream is = new ClassPathResource(path).getInputStream();
			return new String(is.readAllBytes(), StandardCharsets.UTF_8).trim();
		} catch (Exception e) {
			throw new RuntimeException("读取 prompt 文件失败: " + path, e);
		}
	}

	public AllocationPromptPreview buildPreview(Long taskId, Integer topK) {
		log.info("=== PromptBuilder buildPreview() start === taskId={}, topK={}", taskId, topK);
		AllocationTask task = allocationTaskService.findById(taskId);
		AllocationRagContext ragContext = allocationRagContextService.buildContext(taskId, topK);
		List<TimeSlot> timeSlots = timeSlotService.findAll(null, null);
		String outputSchema = buildOutputSchema();
		String systemPrompt = buildSystemPrompt();
		String userPrompt = buildUserPrompt(task, timeSlots, ragContext, outputSchema);
		log.info("Prompt built: sysPrompt={} chars, userPrompt={} chars, teachersInRag={}",
			systemPrompt.length(), userPrompt.length(),
			ragContext.teachers() != null ? ragContext.teachers().size() : 0);
		log.info("=== PromptBuilder buildPreview() end ===");
		return new AllocationPromptPreview(
			task.getId(),
			task.getName(),
			systemPrompt,
			userPrompt,
			outputSchema,
			ragContext
		);
	}

	private String buildSystemPrompt() {
		return readResource("prompts/system-prompt.md");
	}

	private String buildUserPrompt(
		AllocationTask task,
		List<TimeSlot> timeSlots,
		AllocationRagContext ragContext,
		String outputSchema
	) {
		StringBuilder prompt = new StringBuilder();
		appendLine(prompt, "请为以下高校分课任务生成候选分课方案。");
		appendLine(prompt, "");
		appendLine(prompt, "## 分课任务");
		appendLine(prompt, "taskId: " + task.getId());
		appendLine(prompt, "priorityRule: 优先匹配教师可用时间、不可用时间、工作量约束与特殊说明。");
		appendLine(prompt, "additionalRequirements: " + valueOrDefault(task.getDescription(), "无补充要求"));
		appendLine(prompt, "");
		appendLine(prompt, "## 教学任务列表（本分课任务包含以下教学任务，必须按照每个教学任务的 totalHours 分配排课片段）");
		appendLine(prompt, formatTeachingTasks(task));
		appendLine(prompt, "");
		appendLine(prompt, "## 可用时间段（第 " + task.getStartWeek() + " ~ " + task.getEndWeek() + " 周，周一 ~ 周日，每天 5 节：上午 2 节、下午 2 节、晚上 1 节，共 " + timeSlots.size() + " 个）");
		appendLine(prompt, formatTimeSlotSummary(timeSlots, task));
		appendLine(prompt, "");
		appendLine(prompt, "## RAG 检索到的教师画像（topK=" + ragContext.topK() + "）");
		appendLine(prompt, "ragQuery: " + ragContext.query());
		appendLine(prompt, summarize(ragContext.teachers(), ragContext.teachers().size(), this::formatTeacherProfile));
		appendLine(prompt, "");
		appendLine(prompt, "## 固定规则");
		String rules = readResource("prompts/rules.md")
			.replace("{startWeek}", String.valueOf(task.getStartWeek()))
			.replace("{endWeek}", String.valueOf(task.getEndWeek()));
		appendLine(prompt, rules);
		appendLine(prompt, "");
		List<TeachingTask> teachingTasks = task.getTeachingTasks();
		int totalTasks = teachingTasks != null ? teachingTasks.size() : 0;
		int totalItems = teachingTasks != null
			? teachingTasks.stream().mapToInt(tt -> tt.getTotalHours() / 2).sum()
			: 0;
		appendLine(prompt, "## 输出要求");
		appendLine(prompt, "本排课任务共 " + totalTasks + " 个教学任务，总计需要 " + totalItems + " 个排课片段。");
		appendLine(prompt, "请确保 items 数组中包含所有教学任务的全部排课片段，每个教学任务恰好 " + totalHoursPhrase(teachingTasks) + "。");
		appendLine(prompt, "只输出 JSON，业务输出必须符合以下 JSON Schema；items 中不得包含 schema 未列字段：");
		appendLine(prompt, outputSchema);
		return prompt.toString().trim();
	}

	private String buildOutputSchema() {
		return readResource("prompts/output-schema.json");
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

	private String formatTeachingTasks(AllocationTask task) {
		List<TeachingTask> teachingTasks = task.getTeachingTasks();
		if (teachingTasks == null || teachingTasks.isEmpty()) {
			return "无";
		}
		StringBuilder sb = new StringBuilder();
		for (TeachingTask tt : teachingTasks) {
			Course course = tt.getCourse();
			String courseName = course != null ? course.getName() : "未知课程";
			String courseType = course != null ? course.getCourseType() : null;
			String teacherName = tt.getPrimaryTeacher() != null ? tt.getPrimaryTeacher().getName() : "未知教师";
			sb.append("- teachingTaskId=").append(tt.getId())
				.append(", course=").append(courseName);
			if (courseType != null) {
				sb.append("(").append(courseType).append(")");
			}
			sb.append(", teacher=").append(teacherName)
				.append(", totalHours=").append(tt.getTotalHours())
				.append("（需安排 ").append(tt.getTotalHours() / 2).append(" 个片段）");
			// 班级信息
			List<ClassGroup> groups = tt.getClassGroups();
			if (groups != null && !groups.isEmpty()) {
				sb.append(", classes=");
				for (int i = 0; i < groups.size(); i++) {
					ClassGroup g = groups.get(i);
					if (i > 0) sb.append("+");
					sb.append(g.getName()).append("(").append(g.getStudentCount()).append("人)");
				}
			}
			sb.append('\n');
		}
		return sb.toString().trim();
	}

	private String totalHoursPhrase(List<TeachingTask> tasks) {
		if (tasks == null || tasks.isEmpty()) return "0个片段";
		long distinct = tasks.stream().map(tt -> tt.getTotalHours() / 2).distinct().count();
		if (distinct == 1) {
			return tasks.getFirst().getTotalHours() / 2 + "个片段";
		}
		StringBuilder sb = new StringBuilder();
		for (TeachingTask tt : tasks) {
			sb.append("teachingTaskId=").append(tt.getId())
				.append(": ").append(tt.getTotalHours() / 2).append("个, ");
		}
		return sb.substring(0, sb.length() - 2);
	}

	private String formatTimeSlotSummary(List<TimeSlot> timeSlots, AllocationTask task) {
		if (timeSlots.isEmpty()) {
			return "无";
		}
		int startWeek = task.getStartWeek() != null ? task.getStartWeek() : 1;
		int endWeek = task.getEndWeek() != null ? task.getEndWeek() : 18;
		int slotsPerWeek = 35; // 7天 × 5节

		StringBuilder sb = new StringBuilder();
		sb.append("时间段说明：每 ").append(slotsPerWeek).append(" 个 timeSlotId 为一周循环。示例：\n");
		// 取起始周、中间周、结束周的第1个时间段作为示例
		int[] sampleWeeks = {startWeek, (startWeek + endWeek) / 2, endWeek};
		for (int i = 0; i < sampleWeeks.length; i++) {
			int idx = (sampleWeeks[i] - 1) * slotsPerWeek;
			if (idx < timeSlots.size()) {
				TimeSlot ts = timeSlots.get(idx);
				sb.append("- timeSlotId=").append(ts.getId())
					.append(", weekNumber=").append(ts.getWeekNumber())
					.append(", dayOfWeek=").append(ts.getDayOfWeek())
					.append(", periodIndex=").append(ts.getPeriodIndex())
					.append(" (第").append(ts.getWeekNumber()).append("周 周")
					.append(dayName(ts.getDayOfWeek())).append(" 第").append(ts.getPeriodIndex()).append("节)\n");
			}
		}
		// 再加一个晚上第5节的示例
		int eveningIdx = (startWeek - 1) * slotsPerWeek + 4; // 周一第5节（晚上）
		if (eveningIdx < timeSlots.size()) {
			TimeSlot ts = timeSlots.get(eveningIdx);
			sb.append("- timeSlotId=").append(ts.getId())
				.append(", weekNumber=").append(ts.getWeekNumber())
				.append(", dayOfWeek=").append(ts.getDayOfWeek())
				.append(", periodIndex=").append(ts.getPeriodIndex())
				.append(" (第").append(ts.getWeekNumber()).append("周 周")
				.append(dayName(ts.getDayOfWeek())).append(" 第").append(ts.getPeriodIndex()).append("节，晚间)\n");
		}
		sb.append("其他时间段按相同规律类推，timeSlotId 随 weekNumber 递增。所有 weekNumber 均可以在第 ")
			.append(startWeek).append(" ~ ").append(endWeek).append(" 周范围内自由使用。");
		return sb.toString().trim();
	}

	private String dayName(int dayOfWeek) {
		return switch (dayOfWeek) {
			case 1 -> "一"; case 2 -> "二"; case 3 -> "三"; case 4 -> "四";
			case 5 -> "五"; case 6 -> "六"; case 7 -> "日";
			default -> "?";
		};
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
