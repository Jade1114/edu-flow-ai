package com.yuy.eduflow.allocation;

import com.yuy.eduflow.conflict.ConflictCheckResult;
import com.yuy.eduflow.conflict.ConflictCheckResultMapper;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AllocationSchemeGenerationService {
	private static final String CANDIDATE_STATUS = "CANDIDATE";
	private static final String CONFLICT_BIZ_TYPE = "ALLOCATION_ITEM";

	private final AllocationGenerateParseService allocationGenerateParseService;
	private final AllocationSchemeMapper allocationSchemeMapper;
	private final AllocationItemMapper allocationItemMapper;
	private final ConflictCheckResultMapper conflictCheckResultMapper;
	private final AllocationSchemeConflictDetector conflictDetector;

	public AllocationSchemeGenerationService(
		AllocationGenerateParseService allocationGenerateParseService,
		AllocationSchemeMapper allocationSchemeMapper,
		AllocationItemMapper allocationItemMapper,
		ConflictCheckResultMapper conflictCheckResultMapper,
		AllocationSchemeConflictDetector conflictDetector
	) {
		this.allocationGenerateParseService = allocationGenerateParseService;
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.allocationItemMapper = allocationItemMapper;
		this.conflictCheckResultMapper = conflictCheckResultMapper;
		this.conflictDetector = conflictDetector;
	}

	@Transactional
	public AllocationGenerateResult generateSchemes(Long taskId, Integer topK) {
		if (taskId == null) {
			throw new IllegalArgumentException("分课任务ID不能为空");
		}
		if (taskId <= 0) {
			throw new IllegalArgumentException("分课任务ID必须大于0");
		}
		AllocationParsePreview parsePreview = allocationGenerateParseService.generateParsePreview(taskId, topK);
		allocationSchemeMapper.rejectCandidatesByTaskId(taskId);

		List<AllocationScheme> generatedSchemes = new ArrayList<>();
		for (AllocationParsedScheme parsedScheme : safeSchemes(parsePreview)) {
			AllocationScheme scheme = persistScheme(taskId, parsedScheme);
			List<AllocationItem> items = persistItems(scheme.getId(), parsedScheme.items());
			List<AllocationConflictViolation> violations = conflictDetector.detect(items);
			applyItemConflictState(items, violations);
			persistConflictResults(scheme.getId(), violations);
			String conflictSummary = conflictDetector.summarize(violations);
			boolean valid = violations.isEmpty();
			allocationSchemeMapper.updateConflictState(scheme.getId(), valid, conflictSummary);
			generatedSchemes.add(allocationSchemeMapper.findById(scheme.getId()));
		}

		return new AllocationGenerateResult(parsePreview.taskId(), generatedSchemes.size(), generatedSchemes);
	}

	private List<AllocationParsedScheme> safeSchemes(AllocationParsePreview parsePreview) {
		return parsePreview.schemes() == null ? List.of() : parsePreview.schemes();
	}

	private AllocationScheme persistScheme(Long taskId, AllocationParsedScheme parsedScheme) {
		AllocationScheme scheme = new AllocationScheme();
		scheme.setTaskId(taskId);
		scheme.setSchemeName(parsedScheme.schemeName());
		scheme.setSummary(parsedScheme.summary());
		scheme.setScore(parsedScheme.score());
		scheme.setSatisfiedSummary(parsedScheme.satisfiedSummary());
		scheme.setConflictSummary(null);
		scheme.setValid(true);
		scheme.setStatus(CANDIDATE_STATUS);
		allocationSchemeMapper.insert(scheme);
		return scheme;
	}

	private List<AllocationItem> persistItems(Long schemeId, List<AllocationParsedItem> parsedItems) {
		List<AllocationItem> items = new ArrayList<>();
		if (parsedItems == null) {
			return items;
		}
		for (AllocationParsedItem parsedItem : parsedItems) {
			AllocationItem item = new AllocationItem();
			item.setSchemeId(schemeId);
			item.setCourseId(parsedItem.courseId());
			item.setClassGroupId(parsedItem.classGroupId());
			item.setTeacherId(parsedItem.teacherId());
			item.setClassroomId(parsedItem.classroomId());
			item.setTimeSlotId(parsedItem.timeSlotId());
			item.setValid(true);
			item.setConflictMessage(null);
			allocationItemMapper.insert(item);
			items.add(item);
		}
		return items;
	}

	private void applyItemConflictState(List<AllocationItem> items, List<AllocationConflictViolation> violations) {
		Map<Long, List<String>> messagesByItemId = new LinkedHashMap<>();
		for (AllocationConflictViolation violation : violations) {
			messagesByItemId.computeIfAbsent(violation.itemId(), ignored -> new ArrayList<>()).add(violation.message());
		}
		for (AllocationItem item : items) {
			List<String> messages = messagesByItemId.get(item.getId());
			if (messages == null || messages.isEmpty()) {
				continue;
			}
			String conflictMessage = String.join("；", messages);
			item.setValid(false);
			item.setConflictMessage(conflictMessage);
			allocationItemMapper.updateConflictState(item.getId(), false, conflictMessage);
		}
	}

	private void persistConflictResults(Long schemeId, List<AllocationConflictViolation> violations) {
		for (AllocationConflictViolation violation : violations) {
			ConflictCheckResult result = new ConflictCheckResult();
			result.setBizType(CONFLICT_BIZ_TYPE);
			result.setBizId(violation.itemId());
			result.setConflictType(violation.conflictType());
			result.setMessage("方案ID " + schemeId + "：" + violation.message());
			result.setRelatedTeacherId(violation.relatedTeacherId());
			result.setRelatedClassGroupId(violation.relatedClassGroupId());
			result.setRelatedClassroomId(violation.relatedClassroomId());
			result.setRelatedTimeSlotId(violation.relatedTimeSlotId());
			result.setResolved(false);
			conflictCheckResultMapper.insert(result);
		}
	}
}
