package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.OpenAiChatClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
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
		log.info("=== GeneratePreview generate() start === taskId={}, topK={}", taskId, topK);
		long t0 = System.currentTimeMillis();
		AllocationPromptPreview promptPreview = allocationPromptBuilderService.buildPreview(taskId, topK);
		log.info("[{}ms] Prompt built (sys={}c, user={}c)",
			System.currentTimeMillis() - t0, promptPreview.systemPrompt().length(), promptPreview.userPrompt().length());
		log.info("Calling LLM (model={}) with readTimeout=120s...", openAiChatClient.getModelName());
		long start = System.currentTimeMillis();
		String rawResponse = openAiChatClient.generate(promptPreview.systemPrompt(), promptPreview.userPrompt());
		long elapsed = System.currentTimeMillis() - start;
		log.info("LLM responded in {}ms, response length={} chars", elapsed, rawResponse.length());
		log.info("[{}ms] GeneratePreview total (prompt + LLM)", System.currentTimeMillis() - t0);
		log.info("=== GeneratePreview generate() end ===");
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
