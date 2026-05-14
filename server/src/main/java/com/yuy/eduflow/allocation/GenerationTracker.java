package com.yuy.eduflow.allocation;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

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
}
