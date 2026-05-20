package com.yuy.eduflow.allocation;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
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

	private static final long SSE_TIMEOUT_MS = 5 * 60 * 1000L;

	private final Map<Long, GenerationStatus> statusMap = new ConcurrentHashMap<>();
	private final Map<Long, List<SseEmitter>> emitters = new ConcurrentHashMap<>();
	private final ExecutorService executor = Executors.newSingleThreadExecutor();
	private final AllocationSchemeGenerationService generationService;

	public GenerationTracker(AllocationSchemeGenerationService generationService) {
		this.generationService = generationService;
	}

	/**
	 * Start generating schemes for the given task in a background thread.
	 * The status can be polled via {@link #getStatus(Long)}.
	 */
	public void startGeneration(Long taskId) {
		long startedAt = System.currentTimeMillis();
		updateStatus(taskId, running("ml", "开始生成，准备调用自训练排课模型...", 5, startedAt));
		log.info("Generation started for taskId={}", taskId);

		executor.submit(() -> {
			try {
				AllocationGenerateResult result = generationService.generateSchemes(
					taskId,
					status -> updateStatus(taskId, status)
				);
				updateStatus(taskId, new GenerationStatus("COMPLETED", "done", "生成完成", 100, null, result.schemeCount(), null));
				completeEmitters(taskId);
				log.info("Generation completed for taskId={}, schemeCount={}", taskId, result.schemeCount());
			} catch (Exception e) {
				log.error("Generation failed for taskId={}", taskId, e);
				updateStatus(taskId, new GenerationStatus("FAILED", "error", "生成失败", 100, e.getMessage(), 0, null));
				completeEmitters(taskId);
			}
		});
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
		return new GenerationStatus("IDLE", "idle", "尚未开始生成", 0, null, 0, null);
	}

	public void clear(Long taskId) {
		statusMap.remove(taskId);
		completeEmitters(taskId);
	}

	public SseEmitter subscribe(Long taskId) {
		SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
		emitters.computeIfAbsent(taskId, ignored -> new CopyOnWriteArrayList<>()).add(emitter);
		emitter.onCompletion(() -> removeEmitter(taskId, emitter));
		emitter.onTimeout(() -> removeEmitter(taskId, emitter));
		emitter.onError(error -> removeEmitter(taskId, emitter));
		sendStatus(taskId, emitter, getStatus(taskId));
		return emitter;
	}

	private GenerationStatus running(String stage, String message, Integer progress, Long startedAt) {
		return new GenerationStatus("RUNNING", stage, message, progress, null, 0, startedAt);
	}

	private void updateStatus(Long taskId, GenerationStatus status) {
		statusMap.put(taskId, status);
		List<SseEmitter> taskEmitters = emitters.get(taskId);
		if (taskEmitters == null || taskEmitters.isEmpty()) {
			return;
		}
		for (SseEmitter emitter : taskEmitters) {
			sendStatus(taskId, emitter, status);
		}
		// 终态（COMPLETED/FAILED）广播后完成所有 emitter，防止前端卡住
		if ("COMPLETED".equals(status.getStatus()) || "FAILED".equals(status.getStatus())) {
			completeEmitters(taskId);
		}
	}

	private void sendStatus(Long taskId, SseEmitter emitter, GenerationStatus status) {
		try {
			emitter.send(SseEmitter.event().name("status").data(status));
		} catch (IOException | IllegalStateException e) {
			log.debug("SSE send failed for taskId={}", taskId, e);
			removeEmitter(taskId, emitter);
		}
	}

	private void completeEmitters(Long taskId) {
		List<SseEmitter> taskEmitters = emitters.remove(taskId);
		if (taskEmitters == null) {
			return;
		}
		for (SseEmitter emitter : taskEmitters) {
			emitter.complete();
		}
	}

	private void removeEmitter(Long taskId, SseEmitter emitter) {
		List<SseEmitter> taskEmitters = emitters.get(taskId);
		if (taskEmitters == null) {
			return;
		}
		taskEmitters.remove(emitter);
		if (taskEmitters.isEmpty()) {
			emitters.remove(taskId);
		}
	}
}
