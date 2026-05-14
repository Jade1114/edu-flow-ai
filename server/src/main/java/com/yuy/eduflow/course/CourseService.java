package com.yuy.eduflow.course;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.util.StringUtils;

@Service
public class CourseService {
	

	private final CourseMapper courseMapper;

	public CourseService(CourseMapper courseMapper) {
		this.courseMapper = courseMapper;
	}

	public List<Course> findAll(String keyword, String status) {
		return courseMapper.findAll(keyword, status);
	}

	public Course findById(Long id) {
		Course course = courseMapper.findById(id);
		if (course == null) {
			throw new ResourceNotFoundException("课程不存在");
		}
		return course;
	}

	public Course create(CourseRequest request) {
		Course course = toCourse(new Course(), request);
		courseMapper.insert(course);
		return findById(course.getId());
	}

	public Course update(Long id, CourseRequest request) {
		Course existing = findById(id);
		Course course = toCourse(existing, request);
		courseMapper.update(course);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		courseMapper.deactivate(id, ActiveStatus.INACTIVE.code());
	}

	private Course toCourse(Course course, CourseRequest request) {
		if (!StringUtils.hasText(request.name())) {
			throw new ValidationException("课程名称不能为空");
		}
		if (request.requiredHours() != null && request.requiredHours() <= 0) {
			throw new ValidationException("课程课时必须大于0");
		}
		course.setName(request.name().trim());
		course.setCourseType(clean(request.courseType()));
		course.setRequiredHours(request.requiredHours());
		course.setDescription(clean(request.description()));
		course.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : ActiveStatus.ACTIVE.code());
		return course;
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
