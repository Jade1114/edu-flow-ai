package com.yuy.eduflow.allocation;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * Tracks async generation tasks in-memory.
 * When startGeneration is called, the actual generation runs in a background thread
 * and the status map is updated on completion or failure.
 */
@Slf4j
@Service
public class GenerationTracker {

	private final Map<Long, GenerationStatus> statusMap = new ConcurrentHashMap<>();
	private final ExecutorService executor = Executors.newSingleThreadExecutor();
	private final AllocationSchemeGenerationService generationService;

	public GenerationTracker(AllocationSchemeGenerationService generationService) {
		this.generationService = generationService;
	}

	/**
	 * Start generating schemes for the given task in a background thread.
	 * The status can be polled via {@link #getStatus(Long)}.
	 */
	public void startGeneration(Long taskId, Integer topK) {
		statusMap.put(taskId, new GenerationStatus("RUNNING", null, 0, System.currentTimeMillis()));
		log.info("Generation started for taskId={}, topK={}", taskId, topK);

		executor.submit(() -> {
			try {
				AllocationGenerateResult result = generationService.generateSchemes(taskId, topK);
				statusMap.put(taskId, new GenerationStatus("COMPLETED", null, result.schemeCount(), null));
				log.info("Generation completed for taskId={}, schemeCount={}", taskId, result.schemeCount());
			} catch (Exception e) {
				log.error("Generation failed for taskId={}", taskId, e);
				statusMap.put(taskId, new GenerationStatus("FAILED", e.getMessage(), 0, null));
			}
		});
	}

	/**
	 * Start generating schemes with SSE progress streaming.
	 * Creates a SseEmitter, runs generation in background, pushes {@link ProgressEvent} through the emitter.
	 */
	public SseEmitter startGenerationSse(Long taskId, Integer topK) {
		statusMap.put(taskId, new GenerationStatus("RUNNING", null, 0, System.currentTimeMillis()));
		log.info("SSE Generation started for taskId={}, topK={}", taskId, topK);

		SseEmitter emitter = new SseEmitter(300_000L);
		AtomicInteger lastPercent = new AtomicInteger(0);
		ScheduledExecutorService heartbeatScheduler = Executors.newSingleThreadScheduledExecutor();
		ScheduledFuture<?> heartbeatFuture = heartbeatScheduler.scheduleAtFixedRate(() -> {
			sendSse(emitter, ProgressEvent.of("heartbeat", lastPercent.get(), "正在处理..."));
		}, 30, 30, TimeUnit.SECONDS);

		executor.submit(() -> {
			try {
				sendSse(emitter, ProgressEvent.of("rag", 5, "开始生成..."));

				AllocationGenerateResult result = generationService.generateSchemesWithProgress(taskId, topK,
					event -> {
						lastPercent.set(event.percent());
						sendSse(emitter, event);
					});

				heartbeatFuture.cancel(false);
				heartbeatScheduler.shutdown();
				statusMap.put(taskId, new GenerationStatus("COMPLETED", null, result.schemeCount(), null));
				emitter.complete();
				log.info("SSE Generation completed for taskId={}, schemeCount={}", taskId, result.schemeCount());
			} catch (Exception e) {
				log.error("SSE Generation failed for taskId={}", taskId, e);
				heartbeatFuture.cancel(false);
				heartbeatScheduler.shutdown();
				statusMap.put(taskId, new GenerationStatus("FAILED", e.getMessage(), 0, null));
				sendSse(emitter, ProgressEvent.error(e.getMessage()));
				emitter.completeWithError(e);
			}
		});

		return emitter;
	}

	/**
	 * Get the current generation status for a task.
	 * Returns IDLE if no generation has been started for this task.
	 */
	public GenerationStatus getStatus(Long taskId) {
		GenerationStatus s = statusMap.get(taskId);
		if (s != null) {
			return s;
		}
		return new GenerationStatus("IDLE", null, 0, null);
	}

	// ========== SSE 辅助方法 ==========

	private void sendSse(SseEmitter emitter, ProgressEvent event) {
		try {
			emitter.send(SseEmitter.event().name("progress").data(toJson(event)));
		} catch (Exception e) {
			log.warn("Failed to send SSE: stage={}, msg={}", event.stage(), e.getMessage());
		}
	}

	private static String toJson(ProgressEvent event) {
		StringBuilder sb = new StringBuilder();
		sb.append("{\"stage\":\"").append(escape(event.stage())).append("\"");
		sb.append(",\"percent\":").append(event.percent());
		sb.append(",\"message\":\"").append(escape(event.message())).append("\"");
		if (event.schemeIndex() != null) {
			sb.append(",\"schemeIndex\":").append(event.schemeIndex());
		}
		sb.append("}");
		return sb.toString();
	}

	private static String escape(String s) {
		if (s == null) return "";
		return s.replace("\\", "\\\\")
			.replace("\"", "\\\"")
			.replace("\n", "\\n")
			.replace("\r", "\\r")
			.replace("\t", "\\t");
	}
}
