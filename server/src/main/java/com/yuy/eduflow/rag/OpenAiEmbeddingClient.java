package com.yuy.eduflow.rag;

import com.yuy.eduflow.common.exception.ValidationException;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

@Component
public class OpenAiEmbeddingClient {
	private final OpenAiEmbeddingProperties properties;
	private final RestClient.Builder restClientBuilder;

	public OpenAiEmbeddingClient(OpenAiEmbeddingProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClientBuilder = restClientBuilder;
	}

	public List<Double> embed(String input) {
		if (!StringUtils.hasText(input)) {
			throw new ValidationException("向量化文本不能为空");
		}
		if (!StringUtils.hasText(properties.getApiKey())) {
			throw new IllegalStateException("OPENAI_API_KEY 未配置");
		}
		Map<String, Object> response = restClientBuilder
			.baseUrl(properties.getBaseUrl())
			.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
			.defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
			.build()
			.post()
			.uri("/embeddings")
			.body(Map.of(
				"model", properties.getModel(),
				"input", input
			))
			.retrieve()
			.body(Map.class);

		return extractEmbedding(response);
	}

	@SuppressWarnings("unchecked")
	private List<Double> extractEmbedding(Map<String, Object> response) {
		if (response == null || !(response.get("data") instanceof List<?> data) || data.isEmpty()) {
			throw new IllegalStateException("Embedding API 未返回向量数据");
		}
		Object first = data.getFirst();
		if (!(first instanceof Map<?, ?> item) || !(item.get("embedding") instanceof List<?> embedding)) {
			throw new IllegalStateException("Embedding API 返回格式不正确");
		}
		return ((List<?>) embedding).stream()
			.map(value -> ((Number) value).doubleValue())
			.toList();
	}
}
