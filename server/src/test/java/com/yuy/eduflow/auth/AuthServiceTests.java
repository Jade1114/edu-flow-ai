package com.yuy.eduflow.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.yuy.eduflow.teacher.Teacher;
import com.yuy.eduflow.teacher.TeacherMapper;
import org.junit.jupiter.api.Test;

class AuthServiceTests {
	private final TeacherMapper teacherMapper = mock(TeacherMapper.class);
	private final AuthService authService = new AuthService(teacherMapper);

	@Test
	void loginSucceedsWithActiveTeacher() {
		when(teacherMapper.findByEmployeeNo("T1001")).thenReturn(teacher("T1001", "123456", "ACTIVE"));

		LoginResponse result = authService.login(new LoginRequest(" T1001 ", null, "123456"));

		assertThat(result.id()).isEqualTo(7L);
		assertThat(result.teacherId()).isEqualTo(7L);
		assertThat(result.employeeNo()).isEqualTo("T1001");
		assertThat(result.name()).isEqualTo("张明");
		assertThat(result.displayName()).isEqualTo("张明");
		assertThat(result.role()).isEqualTo("TEACHER");
		assertThat(result.department()).isEqualTo("软件工程系");
		assertThat(result.title()).isEqualTo("讲师");
		verify(teacherMapper).findByEmployeeNo("T1001");
	}

	@Test
	void loginRejectsWrongPassword() {
		when(teacherMapper.findByEmployeeNo("T1001")).thenReturn(teacher("T1001", "123456", "ACTIVE"));

		assertThatThrownBy(() -> authService.login(new LoginRequest("T1001", null, "wrong")))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("密码错误");
	}

	@Test
	void loginRejectsInactiveTeacher() {
		when(teacherMapper.findByEmployeeNo("T1001")).thenReturn(teacher("T1001", "123456", "INACTIVE"));

		assertThatThrownBy(() -> authService.login(new LoginRequest("T1001", null, "123456")))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessage("账号状态非 ACTIVE，禁止登录");
	}

	private Teacher teacher(String employeeNo, String password, String status) {
		Teacher teacher = new Teacher();
		teacher.setId(7L);
		teacher.setEmployeeNo(employeeNo);
		teacher.setPassword(password);
		teacher.setRole("TEACHER");
		teacher.setName("张明");
		teacher.setDepartment("软件工程系");
		teacher.setTitle("讲师");
		teacher.setStatus(status);
		return teacher;
	}
}
