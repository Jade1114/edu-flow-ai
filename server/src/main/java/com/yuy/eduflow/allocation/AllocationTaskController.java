package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.ml.MlApiClient;
import java.util.List;
import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api/allocation-tasks")
public class AllocationTaskController {
	private final AllocationTaskService allocationTaskService;
	private final AllocationSchemeService allocationSchemeService;
	private final AllocationSchemeGenerationService allocationSchemeGenerationService;
	private final GenerationTracker generationTracker;
	private final MlApiClient mlApiClient;

	public AllocationTaskController(
		AllocationTaskService allocationTaskService,
		AllocationSchemeService allocationSchemeService,
		AllocationSchemeGenerationService allocationSchemeGenerationService,
		GenerationTracker generationTracker,
		MlApiClient mlApiClient
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationSchemeService = allocationSchemeService;
		this.allocationSchemeGenerationService = allocationSchemeGenerationService;
		this.generationTracker = generationTracker;
		this.mlApiClient = mlApiClient;
	}

	@GetMapping
	public ApiResponse<List<AllocationTask>> findAll(
		@RequestParam(required = false) String keyword,
		@RequestParam(required = false) String status
	) {
		return ApiResponse.success(allocationTaskService.findAll(keyword, status));
	}

	@GetMapping("/{id}")
	public ApiResponse<AllocationTask> findById(@PathVariable Long id) {
		return ApiResponse.success(allocationTaskService.findById(id));
	}

	@GetMapping("/{id}/schemes")
	public ApiResponse<List<AllocationScheme>> findSchemes(@PathVariable Long id) {
		allocationTaskService.findById(id);
		return ApiResponse.success(allocationSchemeService.findAll(id, null));
	}

	@PostMapping("/{id}/schemes")
	public ApiResponse<AllocationGenerateResult> generateSchemes(
		@PathVariable Long id
	) {
		return ApiResponse.success(allocationSchemeGenerationService.generateSchemes(id));
	}

	@PostMapping("/{id}/generate-async")
	public ApiResponse<GenerationStatus> generateAsync(
		@PathVariable Long id
	) {
		generationTracker.startGeneration(id);
		return ApiResponse.success(generationTracker.getStatus(id));
	}

	@GetMapping("/{id}/generation-status")
	public ApiResponse<GenerationStatus> getGenerationStatus(@PathVariable Long id) {
		return ApiResponse.success(generationTracker.getStatus(id));
	}

	@GetMapping(value = "/{id}/generation-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
	public SseEmitter streamGenerationStatus(@PathVariable Long id) {
		SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);
		// 无论成功还是失败，都通过 emitter 发送，不让异常逃逸到 GlobalExceptionHandler
		emitter.onError(ex -> {
			// SSE async error — emitter already removed by tracker
		});
		emitter.onTimeout(() -> {
			// timeout — emitter already removed by tracker
		});
		try {
			SseEmitter subscribed = generationTracker.subscribe(id);
			// 如果 subscribe 返回了新 emitter，用它的 error/timeout 处理
			subscribed.onError(ex -> { /* tracker handles cleanup */ });
			subscribed.onTimeout(() -> { /* tracker handles cleanup */ });
			return subscribed;
		} catch (Exception ex) {
			try {
				emitter.send(SseEmitter.event().name("status").data(
					new GenerationStatus("FAILED", "error", "进度流连接失败", 100, ex.getMessage(), 0, null)
				));
			} catch (Exception ignored) {
				// ignore secondary SSE send failures
			}
			emitter.complete();
			return emitter;
		}
	}

	@PostMapping
	public ApiResponse<AllocationTask> create(@RequestBody AllocationTaskRequest request) {
		return ApiResponse.success(allocationTaskService.create(request));
	}

	@PutMapping("/{id}")
	public ApiResponse<AllocationTask> update(@PathVariable Long id, @RequestBody AllocationTaskRequest request) {
		return ApiResponse.success(allocationTaskService.update(id, request));
	}

	@DeleteMapping("/{id}")
	public ApiResponse<Void> delete(@PathVariable Long id) {
		allocationTaskService.delete(id);
		generationTracker.clear(id);
		return ApiResponse.success();
	}

	// ── LLM Constraint Endpoints ─────────────────────────────────────

	@PostMapping("/{id}/translate-constraint")
	public ApiResponse<Map<String, Object>> translateConstraint(
		@PathVariable Long id,
		@RequestBody Map<String, String> body
	) {
		String text = body.get("text");
		if (text == null || text.isBlank()) {
			return ApiResponse.error(400, "text is required");
		}
		Map<String, Object> result = mlApiClient.translateConstraint(text);
		return ApiResponse.success(result);
	}

	@PutMapping("/{id}/constraints/toggle")
	public ApiResponse<Void> toggleConstraint(
		@PathVariable Long id,
		@RequestBody Map<String, String> body
	) {
		String constraintId = body.get("constraintId");
		AllocationTaskGenerationConfig config = allocationTaskService.getGenerationConfig(id);
		if (config == null) {
			return ApiResponse.error(404, "config not found for task " + id);
		}
		String overridesJson = config.getLlmOverrides();
		if (overridesJson == null || overridesJson.isBlank()) {
			return ApiResponse.error(404, "no llm overrides found");
		}
		allocationTaskService.toggleConstraint(id, constraintId);
		return ApiResponse.success();
	}

	@DeleteMapping("/{id}/constraints/{constraintId}")
	public ApiResponse<Void> deleteConstraint(
		@PathVariable Long id,
		@PathVariable String constraintId
	) {
		allocationTaskService.deleteConstraint(id, constraintId);
		return ApiResponse.success();
	}
}
