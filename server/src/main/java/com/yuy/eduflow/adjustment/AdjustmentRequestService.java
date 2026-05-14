package com.yuy.eduflow.adjustment;

import tools.jackson.core.JsonProcessingException;
import com.yuy.eduflow.assignment.CourseAssignment;
import com.yuy.eduflow.assignment.CourseAssignmentMapper;
import com.yuy.eduflow.assignment.CourseAssignmentService;
import com.yuy.eduflow.common.exception.ConflictException;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Service
public class AdjustmentRequestService {

    private final AdjustmentRequestMapper adjustmentRequestMapper;
    private final CourseAssignmentService courseAssignmentService;
    private final CourseAssignmentMapper courseAssignmentMapper;

    public AdjustmentRequestService(
        AdjustmentRequestMapper adjustmentRequestMapper,
        CourseAssignmentService courseAssignmentService,
        CourseAssignmentMapper courseAssignmentMapper
    ) {
        this.adjustmentRequestMapper = adjustmentRequestMapper;
        this.courseAssignmentService = courseAssignmentService;
        this.courseAssignmentMapper = courseAssignmentMapper;
    }

    // ==================== CRUD ====================

    public List<AdjustmentRequest> findAll(String status, Long teacherId) {
        return adjustmentRequestMapper.findAll(status, teacherId);
    }

    public AdjustmentRequest findById(Long id) {
        AdjustmentRequest req = adjustmentRequestMapper.findById(id);
        if (req == null) throw new ResourceNotFoundException("调课申请不存在");
        return req;
    }

    @Transactional
    public AdjustmentRequest create(AdjustmentRequestRequest request) {
        CourseAssignment assignment = courseAssignmentService.findById(request.assignmentId());

        AdjustmentRequest entity = new AdjustmentRequest();
        entity.setAssignmentId(request.assignmentId());
        entity.setTeacherId(assignment.getTeacherId());
        entity.setReason(request.reason());
        entity.setPreferredTimeText(request.preferredTimeText());
        adjustmentRequestMapper.insert(entity);
        return findById(entity.getId());
    }

    // ==================== AI Suggestions ====================

    /**
     * 生成 AI 调课候选方案。
     * 读取调课申请 + 原课表信息 → 构建 Prompt → 调 LLM → 解析候选 → 检测冲突 → 持久化
     */
    public AdjustmentRequest generateSuggestions(Long requestId) {
        AdjustmentRequest req = findById(requestId);
        CourseAssignment assignment = courseAssignmentService.findById(req.getAssignmentId());

        String prompt = buildPrompt(req, assignment);
        String rawResponse = callLlm(prompt);
        List<AdjustmentSuggestionCandidate> candidates = parseCandidates(rawResponse);
        List<AdjustmentSuggestionCandidate> validated = detectConflicts(assignment, candidates);

        try {
            String json = new ObjectMapper().writeValueAsString(Map.of("candidates", validated));
            adjustmentRequestMapper.updateSuggestion(requestId, json, "PENDING");
        } catch (JsonProcessingException e) {
            throw new ValidationException("候选方案序列化失败");
        }

        return findById(requestId);
    }

    private String buildPrompt(AdjustmentRequest req, CourseAssignment assignment) {
        StringBuilder sb = new StringBuilder();
        sb.append("你是教务调课助手，请根据以下信息生成 2-3 个候选调课方案。\n\n");
        sb.append("【调课申请】\n");
        sb.append("原课程安排ID: ").append(assignment.getId()).append("\n");
        sb.append("调课原因: ").append(req.getReason()).append("\n");
        if (req.getPreferredTimeText() != null) {
            sb.append("调课倾向: ").append(req.getPreferredTimeText()).append("\n");
        }
        sb.append("\n【输出要求】\n");
        sb.append("1. 不改变课程和班级\n");
        sb.append("2. 只调整时间段 (newTimeSlotId) 和教室 (newClassroomId)\n");
        sb.append("3. 尽量满足调课倾向\n");
        sb.append("4. 输出 JSON 格式，顶层键为 candidates，值为数组\n");
        sb.append("5. 每个候选包含: candidateIndex(int), summary(string), newTimeSlotId(long), newClassroomId(long)\n");
        sb.append("6. 生成 ").append(Math.max(2, Math.min(3, 3))).append(" 个候选方案\n");
        return sb.toString();
    }

    private String callLlm(String prompt) {
        // 使用硬编码的系统提示词 + 用户提示词
        String systemPrompt = "你是一个教务调课助手。严格按照输出格式返回 JSON，不要 Markdown 或多余文字。";
        // 暂不引入 OpenAiChatClient 依赖，直接使用硬编码响应便于调试
        // 正式实现时替换为 OpenAiChatClient
        throw new UnsupportedOperationException("暂未接入 LLM，返回模拟数据");
    }

    // ==================== Confirm / Reject ====================

    @Transactional
    public void confirm(Long requestId, AdjustmentConfirmRequest confirmReq) {
        AdjustmentRequest req = findById(requestId);
        adjustmentRequestMapper.updateReview(requestId, "APPROVED", confirmReq.reviewNote());
    }

    @Transactional
    public void reject(Long requestId, AdjustmentRejectRequest rejectReq) {
        AdjustmentRequest req = findById(requestId);
        adjustmentRequestMapper.updateReview(requestId, "REJECTED", rejectReq.reviewNote());
    }
}
