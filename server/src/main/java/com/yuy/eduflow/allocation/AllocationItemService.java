package com.yuy.eduflow.allocation;

import com.yuy.eduflow.classroom.ClassroomService;
import com.yuy.eduflow.timeslot.TimeSlotService;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Slf4j
@Service
public class AllocationItemService {
	private final AllocationItemMapper allocationItemMapper;
	private final AllocationSchemeConflictDetector conflictDetector;
	private final AllocationSchemeMapper allocationSchemeMapper;
	private final ClassroomService classroomService;
	private final TimeSlotService timeSlotService;

	public AllocationItemService(
		AllocationItemMapper allocationItemMapper,
		AllocationSchemeConflictDetector conflictDetector,
		AllocationSchemeMapper allocationSchemeMapper,
		ClassroomService classroomService,
		TimeSlotService timeSlotService
	) {
		this.allocationItemMapper = allocationItemMapper;
		this.conflictDetector = conflictDetector;
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.classroomService = classroomService;
		this.timeSlotService = timeSlotService;
	}

	/**
	 * 更新单条排课片段的位置（教室/时间段），然后重新检测整个方案的冲突。
	 */
	public List<AllocationItemView> moveAndRecheck(Long schemeId, Long itemId, AllocationItemMoveRequest request) {
		log.info("Moving item: schemeId={}, itemId={}, new classroomId={}, new timeSlotId={}",
			schemeId, itemId, request.classroomId(), request.timeSlotId());

		// 1. 校验
		classroomService.findById(request.classroomId());
		timeSlotService.findById(request.timeSlotId());
		AllocationItem item = findById(itemId);
		if (!item.getSchemeId().equals(schemeId)) {
			throw new IllegalArgumentException("该明细不属于此方案");
		}

		// 2. 更新 classroom_id 和 time_slot_id（持久化到数据库）
		item.setClassroomId(request.classroomId());
		item.setTimeSlotId(request.timeSlotId());
		allocationItemMapper.update(item);

		// 3. 重新获取方案所有 items 并检测冲突
		return recheckScheme(schemeId);
	}

	/**
	 * 重新检测整个方案的冲突，返回最新 items。
	 */
	public List<AllocationItemView> recheckScheme(Long schemeId) {
		log.info("Rechecking conflicts for schemeId={}", schemeId);
		List<AllocationItem> allItems = allocationItemMapper.findAll(schemeId, null, null, null);
		List<AllocationConflictViolation> violations = conflictDetector.detect(allItems);
		log.info("Recheck done: {} violations found", violations.size());

		// 应用冲突状态到每个 item
		for (AllocationItem ai : allItems) {
			List<String> msgs = new ArrayList<>();
			for (AllocationConflictViolation v : violations) {
				if (v.itemId().equals(ai.getId())) {
					msgs.add(v.message());
				}
			}
			if (!msgs.isEmpty()) {
				ai.setValid(false);
				ai.setConflictMessage(String.join("；", msgs));
				allocationItemMapper.updateConflictState(ai.getId(), false, ai.getConflictMessage());
			} else {
				ai.setValid(true);
				ai.setConflictMessage(null);
				allocationItemMapper.updateConflictState(ai.getId(), true, null);
			}
		}

		// 更新方案的总体冲突摘要
		boolean hasConflicts = violations.stream().anyMatch(v -> allItems.stream()
			.anyMatch(ai -> ai.getId().equals(v.itemId())));
		String conflictSummary = hasConflicts ? conflictDetector.summarize(violations) : null;
		allocationSchemeMapper.updateConflictState(schemeId, !hasConflicts, conflictSummary);

		return findViewsBySchemeId(schemeId);
	}

	public List<AllocationItem> findAll(
		Long schemeId,
		Long teachingTaskId,
		Long classroomId,
		Long timeSlotId
	) {
		validateOptionalId(schemeId, "分课方案ID必须大于0");
		validateOptionalId(teachingTaskId, "教学任务ID必须大于0");
		validateOptionalId(classroomId, "教室ID必须大于0");
		validateOptionalId(timeSlotId, "时间段ID必须大于0");
		return allocationItemMapper.findAll(schemeId, teachingTaskId, classroomId, timeSlotId);
	}

	public List<AllocationItemView> findViewsBySchemeId(Long schemeId) {
		validateOptionalId(schemeId, "分课方案ID必须大于0");
		return allocationItemMapper.findViewsBySchemeId(schemeId);
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
		AllocationItem existing = findById(id);
		AllocationItem item = toItem(existing, request);
		allocationItemMapper.update(item);
		return findById(id);
	}

	public void delete(Long id) {
		findById(id);
		allocationItemMapper.delete(id);
	}

	private AllocationItem toItem(AllocationItem item, AllocationItemRequest request) {
		requirePositiveId(request.schemeId(), "分课方案ID不能为空");
		requirePositiveId(request.teachingTaskId(), "教学任务ID不能为空");
		requirePositiveId(request.classroomId(), "教室ID不能为空");
		requirePositiveId(request.timeSlotId(), "时间段ID不能为空");
		item.setSchemeId(request.schemeId());
		item.setTeachingTaskId(request.teachingTaskId());
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
