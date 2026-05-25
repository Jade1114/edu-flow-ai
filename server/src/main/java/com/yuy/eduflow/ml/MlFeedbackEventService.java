package com.yuy.eduflow.ml;

import com.yuy.eduflow.allocation.AllocationItem;
import com.yuy.eduflow.allocation.AllocationItemMapper;
import com.yuy.eduflow.allocation.AllocationScheme;
import com.yuy.eduflow.allocation.AllocationSchemeMapper;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Service
public class MlFeedbackEventService {
	public static final String SCHEME_CONFIRMED = "SCHEME_CONFIRMED";
	public static final String ITEM_MOVED = "ITEM_MOVED";
	public static final String ITEM_MARKED_GOOD = "ITEM_MARKED_GOOD";
	public static final String ITEM_MARKED_BAD = "ITEM_MARKED_BAD";

	private final MlFeedbackEventMapper eventMapper;
	private final AllocationSchemeMapper schemeMapper;
	private final AllocationItemMapper itemMapper;
	private final ObjectMapper objectMapper;

	public MlFeedbackEventService(
		MlFeedbackEventMapper eventMapper,
		AllocationSchemeMapper schemeMapper,
		AllocationItemMapper itemMapper,
		ObjectMapper objectMapper
	) {
		this.eventMapper = eventMapper;
		this.schemeMapper = schemeMapper;
		this.itemMapper = itemMapper;
		this.objectMapper = objectMapper;
	}

	public void recordSchemeConfirmed(AllocationScheme scheme, Long feedbackId) {
		if (scheme == null) {
			return;
		}
		MlFeedbackEvent event = baseEvent(SCHEME_CONFIRMED, scheme, null);
		event.setReasonCode("SCHEME_CONFIRMED");
		event.setReasonText("方案被最终确认");
		event.setContextSnapshotJson(toJson(contextSnapshot(scheme, Map.of("feedback_id", feedbackId))));
		eventMapper.insert(event);
	}

	public void recordItemMoved(
		Long schemeId,
		AllocationItem beforeItem,
		AllocationItem afterItem,
		Long adjustmentLogId,
		String reasonText
	) {
		AllocationScheme scheme = findScheme(schemeId);
		AllocationItem item = afterItem != null ? afterItem : beforeItem;
		if (item == null) {
			return;
		}
		MlFeedbackEvent event = baseEvent(ITEM_MOVED, scheme, item);
		event.setReasonCode("ITEM_MOVED");
		event.setReasonText(StringUtils.hasText(reasonText) ? reasonText : "片段被手动移动");
		event.setBeforeSnapshotJson(toJson(itemSnapshot(beforeItem)));
		event.setAfterSnapshotJson(toJson(itemSnapshot(afterItem)));
		Map<String, Object> source = new LinkedHashMap<>();
		if (adjustmentLogId != null) {
			source.put("adjustment_log_id", adjustmentLogId);
		}
		event.setContextSnapshotJson(toJson(contextSnapshot(scheme, source)));
		eventMapper.insert(event);
	}

	public MlFeedbackEvent markItem(Long schemeId, Long itemId, MlFeedbackEventMarkRequest request) {
		if (request == null) {
			throw new ValidationException("标注请求不能为空");
		}
		AllocationScheme scheme = findScheme(schemeId);
		AllocationItem item = itemMapper.findById(itemId);
		if (item == null || !schemeId.equals(item.getSchemeId())) {
			throw new ResourceNotFoundException("分课明细不存在");
		}
		String eventType = resolveMarkEventType(request.markType());
		MlFeedbackEvent event = baseEvent(eventType, scheme, item);
		event.setReasonCode(clean(request.reasonCode()));
		event.setReasonText(clean(request.reasonText()));
		event.setAfterSnapshotJson(toJson(itemSnapshot(item)));
		event.setContextSnapshotJson(toJson(contextSnapshot(scheme, Map.of())));
		eventMapper.insert(event);
		return event;
	}

	public MlFeedbackEventSummary summary(Long taskId, int recentLimit) {
		return new MlFeedbackEventSummary(
			eventMapper.countAll(taskId),
			eventMapper.summarizeByEventType(taskId),
			eventMapper.findRecent(taskId, Math.max(1, Math.min(recentLimit, 100)))
		);
	}

	private MlFeedbackEvent baseEvent(String eventType, AllocationScheme scheme, AllocationItem item) {
		MlFeedbackEvent event = new MlFeedbackEvent();
		event.setEventType(eventType);
		event.setTaskId(scheme.getTaskId());
		event.setSchemeId(scheme.getId());
		event.setActorType("ADMIN");
		if (item != null) {
			event.setItemId(item.getId());
			event.setTeachingTaskId(item.getTeachingTaskId());
		}
		return event;
	}

	private AllocationScheme findScheme(Long schemeId) {
		AllocationScheme scheme = schemeMapper.findById(schemeId);
		if (scheme == null) {
			throw new ResourceNotFoundException("分课方案不存在");
		}
		return scheme;
	}

	private String resolveMarkEventType(String markType) {
		String normalized = StringUtils.hasText(markType) ? markType.trim().toUpperCase() : "";
		return switch (normalized) {
			case "GOOD", "ITEM_MARKED_GOOD" -> ITEM_MARKED_GOOD;
			case "BAD", "ITEM_MARKED_BAD" -> ITEM_MARKED_BAD;
			default -> throw new ValidationException("未知标注类型: " + markType);
		};
	}

	private Map<String, Object> itemSnapshot(AllocationItem item) {
		if (item == null) {
			return Map.of();
		}
		Map<String, Object> snapshot = new LinkedHashMap<>();
		Map<String, Object> itemData = new LinkedHashMap<>();
		itemData.put("id", item.getId());
		itemData.put("scheme_id", item.getSchemeId());
		itemData.put("teaching_task_id", item.getTeachingTaskId());
		itemData.put("classroom_id", item.getClassroomId());
		itemData.put("time_slot_id", item.getTimeSlotId());
		itemData.put("valid", item.getValid());
		itemData.put("conflict_message", item.getConflictMessage());
		itemData.put("profile_penalty_message", Boolean.TRUE.equals(item.getValid()) ? item.getConflictMessage() : null);
		snapshot.put("item", itemData);
		return snapshot;
	}

	private Map<String, Object> contextSnapshot(AllocationScheme scheme, Map<String, Object> extra) {
		Map<String, Object> snapshot = new LinkedHashMap<>();
		Map<String, Object> schemeData = new LinkedHashMap<>();
		schemeData.put("id", scheme.getId());
		schemeData.put("task_id", scheme.getTaskId());
		schemeData.put("scheme_name", scheme.getSchemeName());
		schemeData.put("scheme_score", scheme.getSchemeScore());
		schemeData.put("valid", scheme.getValid());
		schemeData.put("status", scheme.getStatus() == null ? null : scheme.getStatus().code());
		schemeData.put("conflict_summary", scheme.getConflictSummary());
		schemeData.put("model_version", scheme.getModelVersion());
		snapshot.put("scheme", schemeData);
		snapshot.put("evaluation_summary", scheme.getEvaluationSummary());
		if (extra != null && !extra.isEmpty()) {
			snapshot.put("source", extra);
		}
		return snapshot;
	}

	private String toJson(Map<String, Object> payload) {
		try {
			return objectMapper.writeValueAsString(payload);
		} catch (Exception e) {
			log.warn("Failed to serialize feedback event snapshot: {}", e.getMessage());
			return "{}";
		}
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
