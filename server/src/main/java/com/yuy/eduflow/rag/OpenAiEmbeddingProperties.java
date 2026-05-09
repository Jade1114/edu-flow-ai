package com.yuy.eduflow.rag;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "app.embedding.openai")
public class OpenAiEmbeddingProperties {
	private String apiKey;
	private String baseUrl;
	private String model;
}
