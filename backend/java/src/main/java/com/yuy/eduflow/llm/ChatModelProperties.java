package com.yuy.eduflow.llm;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "app.chat.openai")
public class ChatModelProperties {
	private String apiKey;
	private String baseUrl;
	private String model;
}
