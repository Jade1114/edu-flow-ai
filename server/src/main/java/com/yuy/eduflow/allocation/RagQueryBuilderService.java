package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classgroup.ClassGroup;
import com.yuy.eduflow.teachingtask.TeachingTask;
import java.util.List;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * RAG 查询构建器。
 * <p>
 * 只取当前分课任务涉及的教学任务信息（课程、教师、班级）构造查询文本，
 * 不再全量 dump 数据库中的所有课程/班级/教室/时间段。
 * 独立于 {@link AllocationRagContextService}，方便测试和策略切换。
 */
@Slf4j
@Service
public class RagQueryBuilderService {

	/**
	 * 构建 RAG 检索查询文本。
	 * 仅包含当前分课任务涉及的教学任务信息，不 dump 全量数据。
	 *
	 * @param task 当前分课任务（需已加载 teachingTasks）
	 * @return 可用于向量检索的自然语言查询字符串
	 */
	public String buildQuery(AllocationTask task) {
		List<TeachingTask> teachingTasks = task.getTeachingTasks();

		StringBuilder query = new StringBuilder();
		appendLine(query, "任务类型：MVP 分课任务教师画像检索。");
		appendLine(query, "任务名称：" + task.getName());
		appendLine(query, "任务说明：" + valueOrDefault(task.getDescription(), "未提供"));

		if (teachingTasks != null && !teachingTasks.isEmpty()) {
			appendLine(query, "涉及教学任务（共 " + teachingTasks.size() + " 个）：");
			for (TeachingTask tt : teachingTasks) {
				String courseName = tt.getCourse() != null ? tt.getCourse().getName() : "未知课程";
				String teacherName = tt.getPrimaryTeacher() != null ? tt.getPrimaryTeacher().getName() : "未知教师";
				StringBuilder sb = new StringBuilder();
				sb.append("  - 课程：").append(courseName);
				sb.append("，教师：").append(teacherName);
				sb.append("，课时：").append(tt.getTotalHours());
				List<ClassGroup> groups = tt.getClassGroups();
				if (groups != null && !groups.isEmpty()) {
					sb.append("，班级：");
					sb.append(groups.stream().map(ClassGroup::getName).collect(Collectors.joining("+")));
				}
				appendLine(query, sb.toString());
			}
		} else {
			appendLine(query, "涉及教学任务：无");
		}

		appendLine(query, "分课优先规则：优先匹配教师可用时间、不可用时间、工作量约束与特殊说明。");
		appendLine(query, "检索目标说明：从 ACTIVE 教师画像中检索最适合当前分课任务的教师，重点关注可用/不可用时间、工作量要求和特殊约束。");
		return query.toString().trim();
	}

	private String valueOrDefault(String value, String defaultValue) {
		return StringUtils.hasText(value) ? value.trim() : defaultValue;
	}

	private void appendLine(StringBuilder builder, String value) {
		builder.append(value).append('\n');
	}
}
