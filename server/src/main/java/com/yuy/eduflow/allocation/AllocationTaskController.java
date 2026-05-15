package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import java.util.List;
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
	private final AllocationRagContextService allocationRagContextService;
	private final AllocationPromptBuilderService allocationPromptBuilderService;
	private final AllocationGeneratePreviewService allocationGeneratePreviewService;
	private final AllocationGenerateParseService allocationGenerateParseService;
	private final AllocationSchemeGenerationService allocationSchemeGenerationService;
	private final GenerationTracker generationTracker;

	public AllocationTaskController(
		AllocationTaskService allocationTaskService,
		AllocationSchemeService allocationSchemeService,
		AllocationRagContextService allocationRagContextService,
		AllocationPromptBuilderService allocationPromptBuilderService,
		AllocationGeneratePreviewService allocationGeneratePreviewService,
		AllocationGenerateParseService allocationGenerateParseService,
		AllocationSchemeGenerationService allocationSchemeGenerationService,
		GenerationTracker generationTracker
	) {
		this.allocationTaskService = allocationTaskService;
		this.allocationSchemeService = allocationSchemeService;
		this.allocationRagContextService = allocationRagContextService;
		this.allocationPromptBuilderService = allocationPromptBuilderService;
		this.allocationGeneratePreviewService = allocationGeneratePreviewService;
		this.allocationGenerateParseService = allocationGenerateParseService;
		this.allocationSchemeGenerationService = allocationSchemeGenerationService;
		this.generationTracker = generationTracker;
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

	@GetMapping("/{id}/rag-context")
	public ApiResponse<AllocationRagContext> buildRagContext(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationRagContextService.buildContext(id, topK));
	}

	@GetMapping("/{id}/prompt-preview")
	public ApiResponse<AllocationPromptPreview> buildPromptPreview(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationPromptBuilderService.buildPreview(id, topK));
	}

	@PostMapping("/{id}/generate-preview")
	public ApiResponse<AllocationGeneratePreview> generatePreview(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationGeneratePreviewService.generate(id, topK));
	}

	@PostMapping("/{id}/generate-parse-preview")
	public ApiResponse<AllocationParsePreview> generateParsePreview(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationGenerateParseService.generateParsePreview(id, topK));
	}

	@PostMapping("/{id}/schemes")
	public ApiResponse<AllocationGenerateResult> generateSchemes(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK
	) {
		return ApiResponse.success(allocationSchemeGenerationService.generateSchemes(id, topK));
	}

	@PostMapping("/{id}/generate-async")
	public ApiResponse<GenerationStatus> generateAsync(
		@PathVariable Long id,
		@RequestParam(required = false) Integer topK,
		@RequestParam(required = false) String policy
	) {
		generationTracker.startGeneration(id, topK, policy);
		return ApiResponse.success(generationTracker.getStatus(id));
	}

	@GetMapping("/{id}/generation-status")
	public ApiResponse<GenerationStatus> getGenerationStatus(@PathVariable Long id) {
		return ApiResponse.success(generationTracker.getStatus(id));
	}

	@GetMapping(value = "/{id}/generation-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
	public SseEmitter streamGenerationStatus(@PathVariable Long id) {
		SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);
		try {
			return generationTracker.subscribe(id);
		} catch (Exception exception) {
			try {
				emitter.send(SseEmitter.event().name("status").data(
					new GenerationStatus("FAILED", "error", "进度流连接失败", 100, exception.getMessage(), 0, null)
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
		return ApiResponse.success();
	}
}
