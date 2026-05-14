package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.OpenAiChatClient;
import java.util.function.Consumer;
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
		return generate(taskId, topK, ignored -> {});
	}

	public AllocationGeneratePreview generate(Long taskId, Integer topK, Consumer<GenerationStatus> progressReporter) {
		log.info("=== GeneratePreview generate() start === taskId={}, topK={}", taskId, topK);
		long t0 = System.currentTimeMillis();
		progressReporter.accept(running("rag", "检索教师画像与任务约束...", 15));
		AllocationPromptPreview promptPreview = allocationPromptBuilderService.buildPreview(taskId, topK);
		progressReporter.accept(running("prompt", "构建 AI 分课 Prompt...", 30));
		log.info("[{}ms] Prompt built (sys={}c, user={}c)",
			System.currentTimeMillis() - t0, promptPreview.systemPrompt().length(), promptPreview.userPrompt().length());
		log.info("Calling LLM (model={}) with readTimeout=120s...", openAiChatClient.getModelName());
		progressReporter.accept(running("llm", "等待模型生成候选方案...", 45));
		long start = System.currentTimeMillis();
		String rawResponse = openAiChatClient.generate(promptPreview.systemPrompt(), promptPreview.userPrompt());
		long elapsed = System.currentTimeMillis() - start;
		progressReporter.accept(running("parse", "模型已返回，准备解析 JSON...", 60));
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

	private GenerationStatus running(String stage, String message, Integer progress) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, null);
	}
}
