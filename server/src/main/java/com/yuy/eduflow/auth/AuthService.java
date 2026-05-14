package com.yuy.eduflow.auth;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherMapper;
import java.util.Objects;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.util.StringUtils;

@Service
public class AuthService {
	
	private static final String DEFAULT_ROLE = "TEACHER";

	private final TeacherMapper teacherMapper;

	public AuthService(TeacherMapper teacherMapper) {
		this.teacherMapper = teacherMapper;
	}

	public LoginResponse login(LoginRequest request) {
		if (request == null) {
			throw new ValidationException("登录请求不能为空");
		}
		String employeeNo = loginEmployeeNo(request);
		if (!StringUtils.hasText(employeeNo)) {
			throw new ValidationException("工号不能为空");
		}
		if (!StringUtils.hasText(request.password())) {
			throw new ValidationException("密码不能为空");
		}

		Teacher teacher = teacherMapper.findByEmployeeNo(employeeNo);
		if (teacher == null) {
			throw new ResourceNotFoundException("工号不存在");
		}
		if (!Objects.equals(teacher.getPassword(), request.password().trim())) {
			throw new ValidationException("密码错误");
		}
		if (!ActiveStatus.ACTIVE.code().equals(teacher.getStatus())) {
			throw new ValidationException("账号状态非 ACTIVE，禁止登录");
		}

		String role = StringUtils.hasText(teacher.getRole()) ? teacher.getRole() : DEFAULT_ROLE;
		return new LoginResponse(
			teacher.getId(),
			teacher.getEmployeeNo(),
			teacher.getName(),
			teacher.getName(),
			role,
			teacher.getId(),
			teacher.getDepartment(),
			teacher.getTitle()
		);
	}

	private String loginEmployeeNo(LoginRequest request) {
		if (StringUtils.hasText(request.employeeNo())) {
			return request.employeeNo().trim();
		}
		return StringUtils.hasText(request.username()) ? request.username().trim() : null;
	}
}
