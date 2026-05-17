package com.yuy.eduflow.allocation;

import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.rag.OpenAiChatClient;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Pattern;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@RestController
@RequestMapping("/api/param")
public class PolicyTranslateController {

	private static final Pattern INDIVIDUAL_REQUIREMENT_PATTERN = Pattern.compile("(老师|教师|同学|学生|班|课程|[\\u4e00-\\u9fa5]{2,4}(老师|教师))");

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
		if (containsIndividualRequirement(extraRequirement)) {
			throw new BusinessException(400, "全局策略只支持整体排课偏好，例如减少上午、减少周末、更紧凑。某位教师/班级/课程的特殊要求请维护到教师画像或对应基础数据中。");
		}

		String systemPrompt = readResource("prompts/policy-translate-system.md");
		String userPrompt = readResource("prompts/policy-translate-user-template.md")
			.replace("{policyType}", policyType)
			.replace("{extraRequirement}", extraRequirement != null && !extraRequirement.isBlank() ? extraRequirement : "无");

		try {
			String llmResponse = chatClient.generate(systemPrompt, userPrompt);
			@SuppressWarnings("unchecked")
			Map<String, Object> result = objectMapper.readValue(llmResponse, Map.class);
			Map<String, Object> response = new LinkedHashMap<>();
			response.put("policyParams", result.get("policyParams"));
			response.put("interpretation", result.getOrDefault("interpretation", "已根据您的需求生成排课策略参数"));
			log.info("Policy translation: policyType={}, requirement={}, params={}, interpretation={}",
				policyType, extraRequirement, result.get("policyParams"), result.get("interpretation"));
			return ApiResponse.success(response);
		} catch (Exception e) {
			log.error("Policy translation failed", e);
			throw new BusinessException(500, "策略参数翻译失败: " + e.getMessage(), e);
		}
	}

	private boolean containsIndividualRequirement(String requirement) {
		return requirement != null && INDIVIDUAL_REQUIREMENT_PATTERN.matcher(requirement).find();
	}

	private String readResource(String path) {
		try {
			InputStream inputStream = new ClassPathResource(path).getInputStream();
			return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8).trim();
		} catch (Exception e) {
			throw new BusinessException(500, "读取策略翻译 Prompt 失败: " + path, e);
		}
	}
}
