package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.Assert;
import com.yuy.eduflow.conflict.ConflictCheckResult;
import com.yuy.eduflow.conflict.ConflictCheckResultMapper;
import com.yuy.eduflow.teachingtask.TeachingTaskMapper;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import com.yuy.eduflow.enums.SchemeStatus;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class AllocationSchemeGenerationService {
	
	private static final String CONFLICT_BIZ_TYPE = "ALLOCATION_ITEM";

	private final AllocationMlSchemeService allocationMlSchemeService;
	private final AllocationSchemeMapper allocationSchemeMapper;
	private final AllocationItemMapper allocationItemMapper;
	private final ConflictCheckResultMapper conflictCheckResultMapper;
	private final AllocationSchemeConflictDetector conflictDetector;
	private final TeachingTaskMapper teachingTaskMapper;

	public AllocationSchemeGenerationService(
		AllocationMlSchemeService allocationMlSchemeService,
		AllocationSchemeMapper allocationSchemeMapper,
		AllocationItemMapper allocationItemMapper,
		ConflictCheckResultMapper conflictCheckResultMapper,
		AllocationSchemeConflictDetector conflictDetector,
		TeachingTaskMapper teachingTaskMapper
	) {
		this.allocationMlSchemeService = allocationMlSchemeService;
		this.allocationSchemeMapper = allocationSchemeMapper;
		this.allocationItemMapper = allocationItemMapper;
		this.conflictCheckResultMapper = conflictCheckResultMapper;
		this.conflictDetector = conflictDetector;
		this.teachingTaskMapper = teachingTaskMapper;
	}

	public AllocationGenerateResult generateSchemes(Long taskId) {
		return generateSchemes(taskId, ignored -> {});
	}

	public AllocationGenerateResult generateSchemes(Long taskId, Consumer<GenerationStatus> progressReporter) {
		log.info("=== SchemeGeneration generateSchemes() start === taskId={}", taskId);
		Assert.positiveId(taskId, "分课任务ID");
		AllocationGenerationPreview generationPreview = allocationMlSchemeService.generateSchemes(taskId, progressReporter);
		log.info("Parsed {} schemes from self-trained model, rejecting old candidates...",
			generationPreview.schemes() != null ? generationPreview.schemes().size() : 0);
		progressReporter.accept(running("persist", "清理旧候选方案，准备入库...", 70));
		allocationSchemeMapper.rejectCandidatesByTaskId(taskId, SchemeStatus.CANDIDATE.code(), SchemeStatus.REJECTED.code());
		log.info("Old candidates rejected");

		List<AllocationParsedScheme> parsedSchemes = safeSchemes(generationPreview);
		List<AllocationScheme> generatedSchemes = new ArrayList<>();
		for (int i = 0; i < parsedSchemes.size(); i++) {
			AllocationParsedScheme parsedScheme = parsedSchemes.get(i);
			int baseProgress = 75 + Math.round((i * 15f) / Math.max(parsedSchemes.size(), 1));
			progressReporter.accept(running("persist", "保存候选方案 " + (i + 1) + "/" + parsedSchemes.size() + "...", baseProgress));
			log.info("Persisting scheme [{}]...", parsedScheme.schemeName());
			AllocationScheme scheme = persistScheme(taskId, parsedScheme);
			log.info("Scheme persisted: id={}, name={}", scheme.getId(), scheme.getSchemeName());
			List<AllocationItem> items = persistItems(scheme.getId(), parsedScheme.items());
			log.info("Persisted {} items for scheme id={}", items.size(), scheme.getId());
			progressReporter.accept(running("conflict", "检测方案冲突 " + (i + 1) + "/" + parsedSchemes.size() + "...", Math.min(baseProgress + 5, 95)));
			List<AllocationConflictViolation> violations = conflictDetector.detect(items);
			log.info("Conflict detection: {} violations found", violations.size());
			applyItemConflictState(items, violations);
			persistConflictResults(scheme.getId(), violations);
			String conflictSummary = conflictDetector.summarize(violations);
			boolean valid = violations.isEmpty();
			allocationSchemeMapper.updateConflictState(scheme.getId(), valid, conflictSummary);
			log.info("Scheme id={}: valid={}, conflictSummary=[{}]", scheme.getId(), valid, conflictSummary);
			generatedSchemes.add(allocationSchemeMapper.findById(scheme.getId()));
		}

		log.info("=== SchemeGeneration generateSchemes() end === totalSchemes={}", generatedSchemes.size());
		return new AllocationGenerateResult(generationPreview.taskId(), generatedSchemes.size(), generatedSchemes);
	}

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}

	private List<AllocationParsedScheme> safeSchemes(AllocationGenerationPreview generationPreview) {
		return generationPreview.schemes() == null ? List.of() : generationPreview.schemes();
	}

	private AllocationScheme persistScheme(Long taskId, AllocationParsedScheme parsedScheme) {
		AllocationScheme scheme = new AllocationScheme();
		scheme.setTaskId(taskId);
		scheme.setSchemeName(parsedScheme.schemeName());
		scheme.setSummary(parsedScheme.summary());
		scheme.setSchemeScore(parsedScheme.schemeScore());
		scheme.setEvaluationSummary(parsedScheme.evaluationSummary());
		scheme.setPolicy(parsedScheme.policy());
		scheme.setModelVersion(parsedScheme.modelVersion());
		scheme.setConflictSummary(null);
		scheme.setValid(true);
		scheme.setStatus(SchemeStatus.CANDIDATE);
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
			item.setTeachingTaskId(parsedItem.teachingTaskId());
			var tt = teachingTaskMapper.findById(parsedItem.teachingTaskId());
			item.setClassroomId(parsedItem.classroomId() != null ? parsedItem.classroomId() : (tt != null ? tt.getClassroomId() : null));
			item.setTimeSlotId(parsedItem.timeSlotId());
			item.setValid(true);
			item.setConflictMessage(parsedItem.conflictMessage());
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
