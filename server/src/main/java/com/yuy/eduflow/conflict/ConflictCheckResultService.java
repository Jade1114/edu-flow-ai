package com.yuy.eduflow.conflict;

import com.yuy.eduflow.common.Assert;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class ConflictCheckResultService {
	private final ConflictCheckResultMapper conflictCheckResultMapper;

	public ConflictCheckResultService(ConflictCheckResultMapper conflictCheckResultMapper) {
		this.conflictCheckResultMapper = conflictCheckResultMapper;
	}

	public List<ConflictCheckResult> findAll(String bizType, Long bizId, String conflictType, Boolean resolved) {
		validateOptionalId(bizId, "业务ID必须大于0");
		return conflictCheckResultMapper.findAll(bizType, bizId, conflictType, resolved);
	}

	public ConflictCheckResult findById(Long id) {
		ConflictCheckResult result = conflictCheckResultMapper.findById(id);
		if (result == null) {
			throw new ResourceNotFoundException("冲突检测结果不存在");
		}
		return result;
	}

	public ConflictCheckResult create(ConflictCheckResultRequest request) {
		ConflictCheckResult result = toConflictCheckResult(new ConflictCheckResult(), request);
		conflictCheckResultMapper.insert(result);
		return findById(result.getId());
	}

	public ConflictCheckResult update(Long id, ConflictCheckResultRequest request) {
		findById(id);
		ConflictCheckResult result = toConflictCheckResult(new ConflictCheckResult(), request);
		result.setId(id);
		conflictCheckResultMapper.update(result);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		conflictCheckResultMapper.delete(id);
	}

	private ConflictCheckResult toConflictCheckResult(ConflictCheckResult result, ConflictCheckResultRequest request) {
		if (!StringUtils.hasText(request.bizType())) {
			throw new ValidationException("业务类型不能为空");
		}
		Assert.positiveId(request.bizId(), "业务ID");
		if (!StringUtils.hasText(request.conflictType())) {
			throw new ValidationException("冲突类型不能为空");
		}
		if (!StringUtils.hasText(request.message())) {
			throw new ValidationException("冲突说明不能为空");
		}
		validateOptionalId(request.relatedTeacherId(), "相关教师ID必须大于0");
		validateOptionalId(request.relatedClassGroupId(), "相关班级ID必须大于0");
		validateOptionalId(request.relatedClassroomId(), "相关教室ID必须大于0");
		validateOptionalId(request.relatedTimeSlotId(), "相关时间段ID必须大于0");
		result.setBizType(request.bizType().trim());
		result.setBizId(request.bizId());
		result.setConflictType(request.conflictType().trim());
		result.setMessage(request.message().trim());
		result.setRelatedTeacherId(request.relatedTeacherId());
		result.setRelatedClassGroupId(request.relatedClassGroupId());
		result.setRelatedClassroomId(request.relatedClassroomId());
		result.setRelatedTimeSlotId(request.relatedTimeSlotId());
		result.setResolved(request.resolved() != null ? request.resolved() : false);
		return result;
	}

	private void validateOptionalId(Long id, String message) {
		if (id != null && id <= 0) {
			throw new ValidationException(message);
		}
	}
}
