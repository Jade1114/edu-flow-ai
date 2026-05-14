package com.yuy.eduflow.classroom;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import org.springframework.stereotype.Service;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.util.StringUtils;

@Service
public class ClassroomService {
	

	private final ClassroomMapper classroomMapper;

	public ClassroomService(ClassroomMapper classroomMapper) {
		this.classroomMapper = classroomMapper;
	}

	public List<Classroom> findAll(String keyword, String status) {
		return classroomMapper.findAll(keyword, status);
	}

	public Classroom findById(Long id) {
		Classroom classroom = classroomMapper.findById(id);
		if (classroom == null) {
			throw new ResourceNotFoundException("教室不存在");
		}
		return classroom;
	}

	public Classroom create(ClassroomRequest request) {
		Classroom classroom = toClassroom(new Classroom(), request);
		classroomMapper.insert(classroom);
		return findById(classroom.getId());
	}

	public Classroom update(Long id, ClassroomRequest request) {
		findById(id);
		Classroom classroom = toClassroom(new Classroom(), request);
		classroom.setId(id);
		classroomMapper.update(classroom);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		classroomMapper.deactivate(id, ActiveStatus.INACTIVE.code());
	}

	private Classroom toClassroom(Classroom classroom, ClassroomRequest request) {
		if (!StringUtils.hasText(request.name())) {
			throw new ValidationException("教室名称不能为空");
		}
		if (request.capacity() != null && request.capacity() <= 0) {
			throw new ValidationException("教室容量必须大于0");
		}
		classroom.setName(request.name().trim());
		classroom.setBuilding(clean(request.building()));
		classroom.setCapacity(request.capacity());
		classroom.setClassroomType(clean(request.classroomType()));
		classroom.setStatus(StringUtils.hasText(request.status()) ? request.status().trim() : ActiveStatus.ACTIVE.code());
		return classroom;
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
