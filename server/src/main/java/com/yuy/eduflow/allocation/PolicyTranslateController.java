package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.rag.OpenAiChatClient;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@RestController
@RequestMapping("/api/param")
public class PolicyTranslateController {

	private final OpenAiChatClient chatClient;
	private final ObjectMapper objectMapper;

	public PolicyTranslateController(OpenAiChatClient chatClient, ObjectMapper objectMapper) {
		this.chatClient = chatClient;
		this.objectMapper = objectMapper;
	}

	@PostMapping("/translate")
	public ApiResponse<Map<String, Object>> translate(@RequestBody Map<String, Object> request) {
		String policyType = (String) request.getOrDefault("policyType", "BALANCED");
		String extraRequirement = (String) request.getOrDefault("extraRequirement", "");
		@SuppressWarnings("unchecked")
		Map<String, Object> teacherProfiles = (Map<String, Object>) request.get("teacherProfiles");

		String systemPrompt = """
			You are a scheduling policy parameter translator for an educational course scheduling system.
			Your job: convert natural language scheduling preferences into structured policy parameters.
			
			Available policy profiles and their weight keys:
			- weekday_load_penalty (0.002-0.012): penalty for uneven weekday distribution
			- room_day_load_penalty (0.004-0.025): penalty for uneven room usage per day
			- room_week_load_penalty (0.001-0.010): penalty for uneven room usage per week
			- task_day_load_penalty (0.005-0.025): penalty for same-task same-day concentration
			- early_period_penalty (0.005-0.04): penalty for early-morning periods
			- late_period_penalty (0.005-0.03): penalty for late-afternoon periods
			- compact_bonus_weight (0.0-0.015): bonus for compressing schedule into fewer days
			- random_jitter (0.001-0.003): small random perturbation for diversity
			- classroom_stickiness_bonus (0.001-0.015): bonus for keeping same teaching task in the same classroom across all periods
			- weekend_penalty (0.0-0.03): penalty for scheduling on Saturday or Sunday
			
			Output ONLY a valid JSON object with:
			{
			  "policyParams": { all 10 weight keys with numeric values },
			  "interpretation": "brief explanation in Chinese of how you understood the requirements"
			}
			""";

		StringBuilder userPrompt = new StringBuilder();
		userPrompt.append("Policy type: ").append(policyType).append("\n");
		if (extraRequirement != null && !extraRequirement.isBlank()) {
			userPrompt.append("Additional requirements: ").append(extraRequirement).append("\n");
		}
		if (teacherProfiles != null && !teacherProfiles.isEmpty()) {
			userPrompt.append("Teacher profiles: ").append(teacherProfiles).append("\n");
		}
		userPrompt.append("\nGenerate the JSON policy parameters now.");

		try {
			String llmResponse = chatClient.generate(systemPrompt, userPrompt.toString());
			@SuppressWarnings("unchecked")
			Map<String, Object> result = objectMapper.readValue(llmResponse, Map.class);
			Map<String, Object> response = new LinkedHashMap<>();
			response.put("policyParams", result.get("policyParams"));
			response.put("interpretation", result.getOrDefault("interpretation", "已根据您的需求生成排课策略参数"));
			log.info("Policy translation: policyType={}, interpretation={}", policyType, result.get("interpretation"));
			return ApiResponse.success(response);
		} catch (Exception e) {
			log.error("Policy translation failed", e);
			throw new BusinessException(500, "策略参数翻译失败: " + e.getMessage(), e);
		}
	}
}
