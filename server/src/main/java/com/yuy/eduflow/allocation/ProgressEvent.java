package com.yuy.eduflow.allocation;

/**
 * SSE progress event payload.
 * Serialized as JSON and pushed to the frontend via SseEmitter.
 */
public record ProgressEvent(
	String stage,       // rag | prompt | llm | parse | persist | scheme_ready | done | error
	int percent,        // 0-100
	String message,     // human-readable status text
	Integer schemeIndex // only set when stage=scheme_ready
) {

	public static ProgressEvent of(String stage, int percent, String message) {
		return new ProgressEvent(stage, percent, message, null);
	}

	public static ProgressEvent schemeReady(int index, String schemeName) {
		return new ProgressEvent("scheme_ready", 0, schemeName, index);
	}

	public static ProgressEvent done(int schemeCount) {
		return new ProgressEvent("done", 100, schemeCount + " 个方案生成完毕", null);
	}

	public static ProgressEvent error(String errorMessage) {
		return new ProgressEvent("error", 0, errorMessage, null);
	}
}
