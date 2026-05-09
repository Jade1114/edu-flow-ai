package com.yuy.eduflow.rag;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

@Component
public class OpenAiChatClient {
	private final ChatModelProperties properties;
	private final RestClient.Builder restClientBuilder;

	public OpenAiChatClient(ChatModelProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClientBuilder = restClientBuilder;
	}

	public String generate(String systemPrompt, String userPrompt) {
		validateConfiguration();
		if (!StringUtils.hasText(systemPrompt)) {
			throw new IllegalArgumentException("系统提示词不能为空");
		}
		if (!StringUtils.hasText(userPrompt)) {
			throw new IllegalArgumentException("用户提示词不能为空");
		}

		Map<String, Object> body = new LinkedHashMap<>();
		body.put("model", properties.getModel());
		body.put("messages", List.of(
			Map.of("role", "system", "content", systemPrompt),
			Map.of("role", "user", "content", userPrompt)
		));
		body.put("response_format", Map.of("type", "json_object"));

		Map<String, Object> response = restClientBuilder
			.baseUrl(properties.getBaseUrl())
			.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
			.defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
			.build()
			.post()
			.uri("/chat/completions")
			.body(body)
			.retrieve()
			.body(Map.class);

		return extractContent(response);
	}

	private void validateConfiguration() {
		if (!StringUtils.hasText(properties.getApiKey())) {
			throw new IllegalArgumentException("OPENAI_CHAT_API_KEY 未配置");
		}
		if (!StringUtils.hasText(properties.getBaseUrl())) {
			throw new IllegalArgumentException("OPENAI_CHAT_BASE_URL 未配置");
		}
		if (!StringUtils.hasText(properties.getModel())) {
			throw new IllegalArgumentException("OPENAI_CHAT_MODEL 未配置");
		}
	}

	@SuppressWarnings("unchecked")
	private String extractContent(Map<String, Object> response) {
		if (response == null || !(response.get("choices") instanceof List<?> choices) || choices.isEmpty()) {
			throw new IllegalStateException("Chat API 未返回候选结果");
		}
		Object first = choices.getFirst();
		if (!(first instanceof Map<?, ?> choice) || !(choice.get("message") instanceof Map<?, ?> message)) {
			throw new IllegalStateException("Chat API 返回格式不正确");
		}
		Object content = message.get("content");
		if (!(content instanceof String rawContent)) {
			throw new IllegalStateException("Chat API 未返回文本内容");
		}
		return rawContent;
	}
}
