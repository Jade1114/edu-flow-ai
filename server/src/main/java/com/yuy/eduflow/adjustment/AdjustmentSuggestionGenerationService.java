package com.yuy.eduflow.adjustment;

import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import com.yuy.eduflow.rag.OpenAiChatClient;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Service
public class AdjustmentSuggestionGenerationService {
	private final AdjustmentSuggestionPromptBuilderService promptBuilderService;
	private final OpenAiChatClient openAiChatClient;
	private final AdjustmentSuggestionParseService parseService;
	private final AdjustmentSuggestionConflictDetector conflictDetector;
	private final CourseAssignmentService courseAssignmentService;
	private final AdjustmentRequestMapper adjustmentRequestMapper;
	private final ObjectMapper objectMapper;

	public AdjustmentSuggestionGenerationService(
		AdjustmentSuggestionPromptBuilderService promptBuilderService,
		OpenAiChatClient openAiChatClient,
		AdjustmentSuggestionParseService parseService,
		AdjustmentSuggestionConflictDetector conflictDetector,
		CourseAssignmentService courseAssignmentService,
		AdjustmentRequestMapper adjustmentRequestMapper,
		ObjectMapper objectMapper
	) {
		this.promptBuilderService = promptBuilderService;
		this.openAiChatClient = openAiChatClient;
		this.parseService = parseService;
		this.conflictDetector = conflictDetector;
		this.courseAssignmentService = courseAssignmentService;
		this.adjustmentRequestMapper = adjustmentRequestMapper;
		this.objectMapper = objectMapper;
	}

	@Transactional
	public AdjustmentSuggestionPreview generateSuggestions(Long requestId, Integer topK) {
		AdjustmentSuggestionPromptPreview promptPreview = promptBuilderService.buildPreview(requestId, topK);
		String rawResponse = openAiChatClient.generate(promptPreview.systemPrompt(), promptPreview.userPrompt());
		AdjustmentSuggestionPreview parsedPreview = parseService.parse(
			promptPreview.requestId(),
			promptPreview.assignmentId(),
			rawResponse
		);
		CourseAssignment originalAssignment = courseAssignmentService.findById(promptPreview.assignmentId());
		List<AdjustmentSuggestionCandidate> candidates = parsedPreview.candidates().stream()
			.map(candidate -> conflictDetector.detect(originalAssignment, candidate))
			.toList();
		String suggestionJson = toSuggestionJson(candidates, parsedPreview.validationMessages());
		if (adjustmentRequestMapper.updateAiSuggestion(promptPreview.requestId(), suggestionJson) != 1) {
			throw new IllegalArgumentException("调课候选结果保存失败");
		}
		return new AdjustmentSuggestionPreview(
			promptPreview.requestId(),
			promptPreview.assignmentId(),
			rawResponse,
			candidates,
			parsedPreview.validationMessages()
		);
	}

	private String toSuggestionJson(
		List<AdjustmentSuggestionCandidate> candidates,
		List<String> validationMessages
	) {
		try {
			return objectMapper.writeValueAsString(new AdjustmentSuggestionSnapshot(candidates, validationMessages));
		} catch (JacksonException exception) {
			throw new IllegalArgumentException("调课候选结果序列化失败：" + exception.getOriginalMessage());
		}
	}
}
