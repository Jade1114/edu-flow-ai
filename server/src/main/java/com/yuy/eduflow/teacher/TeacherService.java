package com.yuy.eduflow.teacher;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class TeacherService {
	private static final String DEFAULT_STATUS = "ACTIVE";

	private final TeacherMapper teacherMapper;

	public TeacherService(TeacherMapper teacherMapper) {
		this.teacherMapper = teacherMapper;
	}

	public List<Teacher> findAll(String keyword, String status) {
		return teacherMapper.findAll(keyword, status);
	}

	public Teacher findById(Long id) {
		Teacher teacher = teacherMapper.findById(id);
		if (teacher == null) {
			throw new IllegalArgumentException("教师不存在");
		}
		return teacher;
	}

	public Teacher create(TeacherRequest request) {
		Teacher teacher = toTeacher(new Teacher(), request);
		teacherMapper.insert(teacher);
		return findById(teacher.getId());
	}

	public Teacher update(Long id, TeacherRequest request) {
		findById(id);
		Teacher teacher = toTeacher(new Teacher(), request);
		teacher.setId(id);
		teacherMapper.update(teacher);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		teacherMapper.deactivate(id);
	}

	private Teacher toTeacher(Teacher teacher, TeacherRequest request) {
		if (!StringUtils.hasText(request.name())) {
			throw new IllegalArgumentException("教师姓名不能为空");
		}
		if (!StringUtils.hasText(request.department())) {
			throw new IllegalArgumentException("所属部门不能为空");
		}
		if (request.maxWeeklyHours() != null && request.maxWeeklyHours() <= 0) {
			throw new IllegalArgumentException("每周最大课时必须大于0");
		}
		teacher.setName(request.name().trim());
		teacher.setDepartment(request.department().trim());
		teacher.setTitle(StringUtils.hasText(request.title()) ? request.title().trim() : null);
		teacher.setMaxWeeklyHours(request.maxWeeklyHours());
		teacher.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : DEFAULT_STATUS);
		return teacher;
	}
}
