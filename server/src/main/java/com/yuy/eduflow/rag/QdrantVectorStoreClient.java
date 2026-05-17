package com.yuy.eduflow.rag;

import com.yuy.eduflow.common.exception.ValidationException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

@Slf4j
@Component
public class QdrantVectorStoreClient {
	private final QdrantProperties properties;
	private final RestClient.Builder restClientBuilder;

	public QdrantVectorStoreClient(QdrantProperties properties, RestClient.Builder restClientBuilder) {
		this.properties = properties;
		this.restClientBuilder = restClientBuilder;
	}

	public void upsert(Long pointId, List<Double> vector, Map<String, Object> payload) {
		validateVector(vector);
		log.info("Qdrant upsert: pointId={}, payload keys={}", pointId, payload.keySet());
		log.debug("Qdrant upsert vectorText=[{}]", payload.get("vectorText"));
		String vectorText = (String) payload.get("vectorText");
		Map<String, Object> point = new LinkedHashMap<>();
		point.put("id", pointId);
		point.put("vector", vector);
		point.put("payload", payload);

		client()
			.put()
			.uri("/collections/{collection}/points?wait=true", properties.getCollection())
			.body(Map.of("points", List.of(point)))
			.retrieve()
			.toBodilessEntity();
		log.info("Qdrant upsert done ✅");
	}

	public List<VectorSearchResult> search(List<Double> vector, int topK, String status) {
		return search(vector, topK, status, List.of());
	}

	public List<VectorSearchResult> search(List<Double> vector, int topK, String status, List<Long> teacherIds) {
		validateVector(vector);
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("vector", vector);
		body.put("limit", topK);
		body.put("with_payload", true);
		body.put("with_vector", false);
		Map<String, Object> filter = buildFilter(status, teacherIds);
		if (!filter.isEmpty()) {
			body.put("filter", filter);
		}

		Map<String, Object> response = client()
			.post()
			.uri("/collections/{collection}/points/search", properties.getCollection())
			.body(body)
			.retrieve()
			.body(Map.class);
		return extractResults(response);
	}

	private Map<String, Object> buildFilter(String status, List<Long> teacherIds) {
		List<Map<String, Object>> must = new ArrayList<>();
		if (StringUtils.hasText(status)) {
			must.add(Map.of(
				"key", "status",
				"match", Map.of("value", status)
			));
		}
		if (teacherIds != null && !teacherIds.isEmpty()) {
			must.add(Map.of(
				"key", "teacherId",
				"match", Map.of("any", teacherIds)
			));
		}
		return must.isEmpty() ? Map.of() : Map.of("must", must);
	}

	private RestClient client() {
		RestClient.Builder builder = restClientBuilder
			.baseUrl(properties.getUrl())
			.defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE);
		if (StringUtils.hasText(properties.getApiKey())) {
			builder.defaultHeader("api-key", properties.getApiKey());
		}
		return builder.build();
	}

	private void validateVector(List<Double> vector) {
		if (vector == null || vector.isEmpty()) {
			throw new ValidationException("向量不能为空");
		}
		if (properties.getVectorSize() != null && vector.size() != properties.getVectorSize()) {
			throw new ValidationException("向量维度必须为 " + properties.getVectorSize());
		}
	}

	@SuppressWarnings("unchecked")
	private List<VectorSearchResult> extractResults(Map<String, Object> response) {
		if (response == null || !(response.get("result") instanceof List<?> result)) {
			throw new IllegalStateException("Qdrant 未返回检索结果");
		}
		List<VectorSearchResult> items = new ArrayList<>();
		for (Object value : result) {
			if (!(value instanceof Map<?, ?> item)) {
				continue;
			}
			Map<String, Object> payload = item.get("payload") instanceof Map<?, ?> rawPayload
				? (Map<String, Object>) rawPayload
				: Map.of();
			items.add(new VectorSearchResult(
				String.valueOf(item.get("id")),
				item.get("score") instanceof Number score ? score.doubleValue() : null,
				longValue(payload.get("teacherId")),
				longValue(payload.get("profileId")),
				stringValue(payload.get("teacherName")),
				stringValue(payload.get("department")),
				stringValue(payload.get("title")),
				stringValue(payload.get("status")),
				stringValue(payload.get("vectorText")),
				payload
			));
		}
		return items;
	}

	private Long longValue(Object value) {
		return value instanceof Number number ? number.longValue() : null;
	}

	private String stringValue(Object value) {
		return value == null ? null : String.valueOf(value);
	}
}
