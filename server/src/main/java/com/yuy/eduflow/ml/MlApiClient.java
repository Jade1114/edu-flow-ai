package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.exception.BusinessException;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * HTTP client for the Python FastAPI ML service.
 *
 * Submits GA job via POST, then waits for result via SSE stream.
 */
@Slf4j
@Component
public class MlApiClient {

	private final MlApiProperties properties;
	private final RestClient restClient;
	private final HttpClient sseClient;

	public MlApiClient(MlApiProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClient = restClientBuilder
			.requestFactory(new SimpleClientHttpRequestFactory())
			.baseUrl(properties.getUrl())
			.build();
		this.sseClient = HttpClient.newBuilder()
			.connectTimeout(Duration.ofSeconds(30))
			.build();
		log.info("MlApiClient initialized: baseUrl={}", properties.getUrl());
	}

	// ── LLM Constraint Translation ───────────────────────────────────

	@SuppressWarnings("unchecked")
	public Map<String, Object> translateConstraint(String text) {
		Map<String, String> body = Map.of("text", text);
		Map<String, Object> response = restClient.post()
			.uri("/api/ml/translate-constraint")
			.contentType(MediaType.APPLICATION_JSON)
			.body(body)
			.retrieve()
			.body(Map.class);
		return response;
	}

	// ── Health ────────────────────────────────────────────────────────

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

	// ── Async GA Generation (SSE) ─────────────────────────────────────

	/**
	 * Submit a GA job via POST, then wait via SSE. Returns output_dir string.
	 */
	public String generateSchemes(Map<String, Object> requestParams) {
		String taskId = submitGenerateSchemes(requestParams);
		return waitForSseOutputDir(taskId);
	}

	private String submitGenerateSchemes(Map<String, Object> requestParams) {
		Object allocationTaskId = requestParams.get("task_id");
		if (allocationTaskId == null) {
			throw new BusinessException(500, "ML API submit missing task_id: " + requestParams);
		}
		log.info("ML API submit generate-scheme: taskId={}", allocationTaskId);

		Map<String, Object> response = restClient.post()
			.uri("/api/ml/generate-scheme")
			.contentType(MediaType.APPLICATION_JSON)
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
		log.info("ML API task submitted: taskId={}", taskId);
		return taskId;
	}

	/**
	 * Read SSE stream until completed/failed event. Returns output_dir string.
	 */
	private String waitForSseOutputDir(String taskId) {
		String streamUrl = properties.getUrl() + "/api/ml/generate-scheme/" + taskId + "/stream";
		log.info("ML API SSE connect: taskId={}", taskId);

		try {
			HttpRequest request = HttpRequest.newBuilder()
				.uri(URI.create(streamUrl))
				.timeout(Duration.ofMinutes(30))
				.GET()
				.build();

			HttpResponse<java.io.InputStream> response = sseClient.send(request,
				HttpResponse.BodyHandlers.ofInputStream());

			try (BufferedReader reader = new BufferedReader(
					new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {

				String currentEvent = null;
				StringBuilder dataBuilder = new StringBuilder();

				String line;
				while ((line = reader.readLine()) != null) {
					if (line.startsWith("event: ")) {
						currentEvent = line.substring(7).trim();
						dataBuilder.setLength(0);
					} else if (line.startsWith("data: ")) {
						if (dataBuilder.length() > 0) dataBuilder.append("\n");
						dataBuilder.append(line.substring(6));
					} else if (line.isEmpty() && currentEvent != null) {
						String data = dataBuilder.toString();

						switch (currentEvent) {
							case "completed" -> {
								String outputDir = extractOutputDir(data);
								if (outputDir == null) {
									throw new BusinessException(500,
										"ML API SSE completed but no output_dir in: " + data);
								}
								log.info("ML API task completed via SSE: taskId={}", taskId);
								return outputDir;
							}
							case "failed" -> {
								String error = extractError(data);
								throw new BusinessException(500,
									"ML API task failed: taskId=" + taskId + ", error=" + error);
							}
							case "progress" -> log.info("ML progress: taskId={} {}", taskId, data);
							case "heartbeat" -> log.debug("SSE heartbeat: taskId={}", taskId);
						}
						currentEvent = null;
						dataBuilder.setLength(0);
					}
				}
			}

			throw new BusinessException(500, "ML API SSE stream ended without completion: taskId=" + taskId);

		} catch (BusinessException e) {
			throw e;
		} catch (Exception e) {
			throw new BusinessException(500, "ML API SSE failed: taskId=" + taskId + ", error=" + e.getMessage());
		}
	}

	/**
	 * Extract "output_dir" value from raw JSON data, without JSON parser.
	 * Handles both "output_dir":"value" and "output_dir": "value".
	 */
	private static String extractOutputDir(String json) {
		// 找 "output_dir":  (flexible spacing)
		String key = "\"output_dir\"";
		int start = json.indexOf(key);
		if (start < 0) return null;
		start = json.indexOf("\"", start + key.length() + 1);  // find opening quote after colon
		if (start < 0) return null;
		start++;
		int end = json.indexOf("\"", start);
		return end > start ? json.substring(start, end) : null;
	}

	/**
	 * Extract error message from failed event JSON.
	 */
	private static String extractError(String json) {
		String key = "\"error\":\"";
		int start = json.indexOf(key);
		if (start < 0) return json;
		start += key.length();
		int end = json.indexOf("\"", start);
		return end > start ? json.substring(start, end) : json;
	}
}
