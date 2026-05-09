package com.yuy.eduflow.rag;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "app.vector-store.qdrant")
public class QdrantProperties {
	private String url;
	private String apiKey;
	private String collection;
	private Integer vectorSize;
}
