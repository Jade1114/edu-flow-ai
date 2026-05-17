package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.course.Course;
import com.yuy.eduflow.enums.TaskStatus;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teachingtask.TeachingTask;
import java.util.List;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AllocationTaskService {
	

	private final AllocationTaskMapper allocationTaskMapper;

	public AllocationTaskService(AllocationTaskMapper allocationTaskMapper) {
		this.allocationTaskMapper = allocationTaskMapper;
	}

	public List<AllocationTask> findAll(String keyword, String status) {
		List<AllocationTask> tasks = allocationTaskMapper.findAll(keyword, status);
		for (AllocationTask task : tasks) {
			task.setTeachingTasks(loadTeachingTasks(task.getId()));
		}
		return tasks;
	}

	public AllocationTask findById(Long id) {
		AllocationTask task = allocationTaskMapper.findById(id);
		if (task == null) {
			throw new ResourceNotFoundException("分课任务不存在");
		}
		task.setTeachingTasks(loadTeachingTasks(id));
		return task;
	}

	private List<TeachingTask> loadTeachingTasks(Long taskId) {
		List<AllocationTaskTeachingTaskResult> results = allocationTaskMapper.findTeachingTasks(taskId);
		return results.stream().map(this::toTeachingTask).collect(Collectors.toList());
	}

	private TeachingTask toTeachingTask(AllocationTaskTeachingTaskResult r) {
		TeachingTask tt = new TeachingTask();
		tt.setId(r.getId());
		tt.setCourseId(r.getCourseId());
		tt.setPrimaryTeacherId(r.getPrimaryTeacherId());
		tt.setAssistantTeacherId(r.getAssistantTeacherId());
		tt.setTotalHours(r.getTotalHours());
		tt.setClassroomId(r.getClassroomId());
		tt.setNotes(r.getNotes());
		tt.setStatus(r.getStatus());
		tt.setCreatedAt(r.getCreatedAt());
		tt.setUpdatedAt(r.getUpdatedAt());

		if (r.getCourseName() != null) {
			Course course = new Course();
			course.setId(r.getCourseId());
			course.setName(r.getCourseName());
			tt.setCourse(course);
		}
		if (r.getPrimaryTeacherName() != null) {
			Teacher teacher = new Teacher();
			teacher.setId(r.getPrimaryTeacherId());
			teacher.setName(r.getPrimaryTeacherName());
			tt.setPrimaryTeacher(teacher);
		}
		if (r.getAssistantTeacherName() != null) {
			Teacher teacher = new Teacher();
			teacher.setId(r.getAssistantTeacherId());
			teacher.setName(r.getAssistantTeacherName());
			tt.setAssistantTeacher(teacher);
		}
		return tt;
	}

    @Transactional
	public AllocationTask create(AllocationTaskRequest request) {
        validateRequest(request);
		AllocationTask task = toTask(new AllocationTask(), request);
		allocationTaskMapper.insert(task);
        if (request.teachingTaskIds() != null) {
            bindTeachingTasks(task.getId(), request.teachingTaskIds());
        }
		return findById(task.getId());
	}

    @Transactional
	public AllocationTask update(Long id, AllocationTaskRequest request) {
		AllocationTask existing = findById(id);
        validateRequest(request);
		AllocationTask task = toTask(existing, request);
		allocationTaskMapper.update(task);
        allocationTaskMapper.deleteTeachingTasks(id);
        if (request.teachingTaskIds() != null) {
            bindTeachingTasks(id, request.teachingTaskIds());
        }
		return findById(id);
	}

    @Transactional
	public void delete(Long id) {
		findById(id);
		allocationTaskMapper.deleteAdjustmentRequestsByTaskId(id);
		allocationTaskMapper.deleteCourseAssignmentsByTaskId(id);
		allocationTaskMapper.deleteConflictsByTaskId(id);
		allocationTaskMapper.deleteAdjustmentLogsByTaskId(id);
		allocationTaskMapper.deleteFeedbackByTaskId(id);
		allocationTaskMapper.deleteItemsByTaskId(id);
		allocationTaskMapper.deleteSchemesByTaskId(id);
        allocationTaskMapper.deleteTeachingTasks(id);
		allocationTaskMapper.deleteById(id);
	}

    private void bindTeachingTasks(Long taskId, List<Long> teachingTaskIds) {
        for (Long teachingTaskId : teachingTaskIds) {
            if (teachingTaskId != null && teachingTaskId > 0) {
                allocationTaskMapper.insertTeachingTask(taskId, teachingTaskId);
            }
        }
    }

	private AllocationTask toTask(AllocationTask task, AllocationTaskRequest request) {
        task.setName(request.name());
        task.setDescription(request.description());
        task.setStartWeek(request.startWeek() != null ? request.startWeek() : 1);
        task.setEndWeek(request.endWeek() != null ? request.endWeek() : 18);
        task.setStatus(
                request.status() != null && !request.status().isBlank() ? TaskStatus.from(request.status().trim()) : TaskStatus.DRAFT);
        task.setCreatedBy(request.createdBy());
		return task;
	}

    private void validateRequest(AllocationTaskRequest request) {
        if (request.name() == null || request.name().isBlank()) {
            throw new ValidationException("任务名称不能为空");
        }
        if (request.startWeek() != null && (request.startWeek() < 1 || request.startWeek() > 18)) {
            throw new ValidationException("起始周次必须在1到18之间");
        }
        if (request.endWeek() != null && (request.endWeek() < 1 || request.endWeek() > 18)) {
            throw new ValidationException("结束周次必须在1到18之间");
        }
        if (request.startWeek() != null && request.endWeek() != null && request.startWeek() > request.endWeek()) {
            throw new ValidationException("起始周次不能大于结束周次");
        }
    }
}
