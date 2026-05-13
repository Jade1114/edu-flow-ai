package com.yuy.eduflow.rag;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

/**
 * OpenAI 兼容 Chat API 客户端。
 * 使用 RestClient 直接反序列化响应，无需手动 JSON 解析。
 */
@Slf4j
@Component
public class OpenAiChatClient {
	private final ChatModelProperties properties;
	private final RestClient.Builder restClientBuilder;

	public OpenAiChatClient(ChatModelProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClientBuilder = restClientBuilder;
	}

	public String getModelName() {
		return properties.getModel();
	}

	public String generate(String systemPrompt, String userPrompt) {
		validateConfiguration();
		if (!StringUtils.hasText(systemPrompt)) {
			throw new IllegalArgumentException("系统提示词不能为空");
		}
		if (!StringUtils.hasText(userPrompt)) {
			throw new IllegalArgumentException("用户提示词不能为空");
		}

		log.info("LLM request: model={}, max_tokens={}, sysPrompt={}chars, userPrompt={}chars",
			properties.getModel(), 8192, systemPrompt.length(), userPrompt.length());
		log.debug("systemPrompt=[{}]", systemPrompt);
		log.debug("userPrompt=[{}]", userPrompt);

		Map<String, Object> body = new LinkedHashMap<>();
		body.put("model", properties.getModel());
		body.put("messages", List.of(
			Map.of("role", "system", "content", systemPrompt),
			Map.of("role", "user", "content", userPrompt)
		));
		body.put("response_format", Map.of("type", "json_object"));
		body.put("temperature", 0.3);
		body.put("max_tokens", 8192);

		var httpClient = HttpClient.newBuilder()
			.connectTimeout(Duration.ofSeconds(30))
			.build();
		var requestFactory = new JdkClientHttpRequestFactory(httpClient);
		requestFactory.setReadTimeout(Duration.ofSeconds(120));

		long start = System.currentTimeMillis();
		ChatResponse response;
		try {
			response = restClientBuilder
				.baseUrl(properties.getBaseUrl())
				.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
				.defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
				.requestFactory(requestFactory)
				.build()
				.post()
				.uri("/chat/completions")
				.body(body)
				.retrieve()
				.body(ChatResponse.class);
		} catch (Exception e) {
			log.error("LLM API 调用异常: {}，模型={}，endpoint={}/chat/completions",
				e.getMessage(), properties.getModel(), properties.getBaseUrl(), e);
			throw e;
		}
		long elapsed = System.currentTimeMillis() - start;

		if (response == null || response.choices() == null || response.choices().isEmpty()) {
			throw new IllegalStateException("LLM 未返回候选结果");
		}
		String content = response.choices().getFirst().message().content();
		if (!StringUtils.hasText(content)) {
			throw new IllegalStateException("LLM 未返回文本内容");
		}

		log.info("LLM response: {}ms, content={}chars", elapsed, content.length());
		return content;
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

	// ====== API 响应 DTO ======

	record ChatResponse(List<Choice> choices) {}
	record Choice(Message message) {}
	record Message(String content) {}
}
