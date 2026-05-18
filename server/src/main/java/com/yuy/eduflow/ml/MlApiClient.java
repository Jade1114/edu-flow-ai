package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.exception.BusinessException;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * HTTP client for the Python FastAPI ML service.
 * Replaces direct subprocess (ProcessBuilder) calls to Python scripts.
 */
@Slf4j
@Component
public class MlApiClient {

	private final MlApiProperties properties;
	private final RestClient restClient;

	public MlApiClient(MlApiProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		String baseUrl = properties.getUrl();
		this.restClient = restClientBuilder
			.baseUrl(baseUrl)
			.build();
		log.info("MlApiClient initialized: baseUrl={}", baseUrl);
	}

	/**
	 * Check if the ML API server is reachable.
	 */
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

	/**
	 * Generate scheduling schemes via the GA pipeline.
	 *
	 * @param requestParams Flat string-keyed map mirroring the FastAPI GenerateSchemeRequest schema.
	 * @return Parsed response map with keys: success, output_dir, scheme_count, schemes, etc.
	 */
	@SuppressWarnings("unchecked")
	public Map<String, Object> generateSchemes(Map<String, Object> requestParams) {
		log.info("ML API generate-scheme request: outputDir={}, variantCount={}, policy={}",
			requestParams.get("output_dir"),
			requestParams.get("variant_count"),
			requestParams.get("policy"));

		long startedAt = System.currentTimeMillis();
		Map<String, Object> response = restClient.post()
			.uri("/api/ml/generate-scheme")
			.header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
			.body(requestParams)
			.retrieve()
			.body(Map.class);

		long elapsed = System.currentTimeMillis() - startedAt;
		if (response == null) {
			throw new BusinessException(500, "ML API returned null response");
		}

		boolean success = Boolean.TRUE.equals(response.get("success"));
		if (!success) {
			String error = (String) response.getOrDefault("error", "unknown ML API error");
			throw new BusinessException(500, "ML API generate-scheme failed: " + error);
		}

		log.info("ML API generate-scheme completed in {}ms: outputDir={}, schemeCount={}",
			elapsed, response.get("output_dir"), response.get("scheme_count"));
		return response;
	}
}
