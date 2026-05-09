package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.OpenAiChatClient;
import org.springframework.stereotype.Service;

@Service
public class AllocationGeneratePreviewService {
	private final AllocationPromptBuilderService allocationPromptBuilderService;
	private final OpenAiChatClient openAiChatClient;

	public AllocationGeneratePreviewService(
		AllocationPromptBuilderService allocationPromptBuilderService,
		OpenAiChatClient openAiChatClient
	) {
		this.allocationPromptBuilderService = allocationPromptBuilderService;
		this.openAiChatClient = openAiChatClient;
	}

	public AllocationGeneratePreview generate(Long taskId, Integer topK) {
		AllocationPromptPreview promptPreview = allocationPromptBuilderService.buildPreview(taskId, topK);
		String rawResponse = openAiChatClient.generate(promptPreview.systemPrompt(), promptPreview.userPrompt());
		return new AllocationGeneratePreview(
			promptPreview.taskId(),
			promptPreview.taskName(),
			promptPreview.systemPrompt(),
			promptPreview.userPrompt(),
			promptPreview.outputSchema(),
			rawResponse
		);
	}
}
