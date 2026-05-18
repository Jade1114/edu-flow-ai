package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.exception.BusinessException;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * HTTP client for the Python FastAPI ML service.
 *
 * Uses the async task pattern: submits a GA job (202 Accepted → task_id),
 * then polls for completion. The caller still sees a blocking
 * {@link #generateSchemes(Map)} call, but internally uses short-lived HTTP
 * connections with polling.
 */
@Slf4j
@Component
public class MlApiClient {

	private static final int POLL_INTERVAL_MS = 3000;
	/** Total max wait for a GA job (~15 min). */
	private static final long MAX_WAIT_MS = 15 * 60 * 1000L;

	private final MlApiProperties properties;
	private final RestClient restClient;

	public MlApiClient(MlApiProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClient = restClientBuilder
			.baseUrl(properties.getUrl())
			.build();
		log.info("MlApiClient initialized: baseUrl={}", properties.getUrl());
	}

	// ── Health ────────────────────────────────────────────────────────

	/** Check if the ML API server is reachable. */
	public boolean health() {
		try {
			@SuppressWarnings("unchecked")
			Map<String, Object> result = restClient.get()
				.uri("/api/ml/health")
				.retrieve()
				.body(Map.class);
			return result != null && "ok".equals(result.get("status"));
		} catch (Exception e) {
			log.warn("ML API health check failed: {}", e.getMessage());
			return false;
		}
	}

	// ── Async GA Generation ──────────────────────────────────────────

	/**
	 * Submit a GA scheme generation job and wait for it to complete.
	 *
	 * Internally: POST → get task_id → poll GET until done.
	 * Total wall time can be several minutes.
	 */
	@SuppressWarnings("unchecked")
	public Map<String, Object> generateSchemes(Map<String, Object> requestParams) {
		String taskId = submitGenerateSchemes(requestParams);
		return pollForResult(taskId);
	}

	/**
	 * Submit a GA scheme generation job and return immediately with a task_id.
	 * Call {@link #getTaskStatus(String)} to poll for the result.
	 */
	public String submitGenerateSchemes(Map<String, Object> requestParams) {
		log.info("ML API submit generate-scheme: outputDir={}, variantCount={}, policy={}",
			requestParams.get("output_dir"),
			requestParams.get("variant_count"),
			requestParams.get("policy"));

		Map<String, Object> response = restClient.post()
			.uri("/api/ml/generate-scheme")
			.header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
			.body(requestParams)
			.retrieve()
			.body(Map.class);

		if (response == null) {
			throw new BusinessException(500, "ML API submit returned null");
		}

		String taskId = (String) response.get("task_id");
		if (taskId == null || taskId.isBlank()) {
			throw new BusinessException(500, "ML API submit returned no task_id: " + response);
		}

		log.info("ML API task submitted: taskId={}, statusUrl={}", taskId, response.get("status_url"));
		return taskId;
	}

	/**
	 * Poll the task status endpoint until the job completes or fails.
	 */
	@SuppressWarnings("unchecked")
	public Map<String, Object> pollForResult(String taskId) {
		long deadline = System.currentTimeMillis() + MAX_WAIT_MS;
		String statusUri = "/api/ml/generate-scheme/" + taskId;

		int attempt = 0;
		while (System.currentTimeMillis() < deadline) {
			attempt++;
			Map<String, Object> status = restClient.get()
				.uri(statusUri)
				.retrieve()
				.body(Map.class);

			if (status == null) {
				throw new BusinessException(500, "ML API task status returned null for taskId=" + taskId);
			}

			String taskStatus = (String) status.get("status");
			log.debug("ML API task poll attempt={} taskId={} status={}", attempt, taskId, taskStatus);

			switch (taskStatus) {
				case "done" -> {
					Object result = status.get("result");
					if (result instanceof Map<?, ?> resultMap) {
						log.info("ML API task completed: taskId={}", taskId);
						return (Map<String, Object>) resultMap;
					}
					throw new BusinessException(500, "ML API task done but result is missing or malformed: taskId=" + taskId);
				}
				case "failed" -> {
					String error = (String) status.getOrDefault("error", "unknown error");
					throw new BusinessException(500, "ML API task failed: taskId=" + taskId + ", error=" + error);
				}
				default -> {
					// pending / running — keep polling
					try {
						Thread.sleep(POLL_INTERVAL_MS);
					} catch (InterruptedException e) {
						Thread.currentThread().interrupt();
						throw new BusinessException(500, "ML API task poll interrupted: taskId=" + taskId);
					}
				}
			}
		}

		throw new BusinessException(500, "ML API task timed out after " + (MAX_WAIT_MS / 1000) + "s: taskId=" + taskId);
	}

	/**
	 * Get current task status without waiting for completion.
	 */
	@SuppressWarnings("unchecked")
	public Map<String, Object> getTaskStatus(String taskId) {
		return restClient.get()
			.uri("/api/ml/generate-scheme/" + taskId)
			.retrieve()
			.body(Map.class);
	}
}
