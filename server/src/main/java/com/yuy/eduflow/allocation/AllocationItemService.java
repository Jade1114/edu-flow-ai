package com.yuy.eduflow.allocation;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class AllocationItemService {
	private final AllocationItemMapper allocationItemMapper;

	public AllocationItemService(AllocationItemMapper allocationItemMapper) {
		this.allocationItemMapper = allocationItemMapper;
	}

	public List<AllocationItem> findAll(
		Long schemeId,
		Long teacherId,
		Long classGroupId,
		Long classroomId,
		Long timeSlotId
	) {
		validateOptionalId(schemeId, "分课方案ID必须大于0");
		validateOptionalId(teacherId, "教师ID必须大于0");
		validateOptionalId(classGroupId, "班级ID必须大于0");
		validateOptionalId(classroomId, "教室ID必须大于0");
		validateOptionalId(timeSlotId, "时间段ID必须大于0");
		return allocationItemMapper.findAll(schemeId, teacherId, classGroupId, classroomId, timeSlotId);
	}

	public AllocationItem findById(Long id) {
		AllocationItem item = allocationItemMapper.findById(id);
		if (item == null) {
			throw new IllegalArgumentException("分课明细不存在");
		}
		return item;
	}

	public AllocationItem create(AllocationItemRequest request) {
		AllocationItem item = toItem(new AllocationItem(), request);
		allocationItemMapper.insert(item);
		return findById(item.getId());
	}

	public AllocationItem update(Long id, AllocationItemRequest request) {
		findById(id);
		AllocationItem item = toItem(new AllocationItem(), request);
		item.setId(id);
		allocationItemMapper.update(item);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		allocationItemMapper.delete(id);
	}

	private AllocationItem toItem(AllocationItem item, AllocationItemRequest request) {
		requirePositiveId(request.schemeId(), "分课方案ID不能为空");
		requirePositiveId(request.courseId(), "课程ID不能为空");
		requirePositiveId(request.classGroupId(), "班级ID不能为空");
		requirePositiveId(request.teacherId(), "教师ID不能为空");
		requirePositiveId(request.classroomId(), "教室ID不能为空");
		requirePositiveId(request.timeSlotId(), "时间段ID不能为空");
		item.setSchemeId(request.schemeId());
		item.setCourseId(request.courseId());
		item.setClassGroupId(request.classGroupId());
		item.setTeacherId(request.teacherId());
		item.setClassroomId(request.classroomId());
		item.setTimeSlotId(request.timeSlotId());
		item.setValid(request.valid() != null ? request.valid() : true);
		item.setConflictMessage(clean(request.conflictMessage()));
		return item;
	}

	private void requirePositiveId(Long id, String emptyMessage) {
		if (id == null) {
			throw new IllegalArgumentException(emptyMessage);
		}
		if (id <= 0) {
			throw new IllegalArgumentException(emptyMessage.replace("不能为空", "必须大于0"));
		}
	}

	private void validateOptionalId(Long id, String message) {
		if (id != null && id <= 0) {
			throw new IllegalArgumentException(message);
		}
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
