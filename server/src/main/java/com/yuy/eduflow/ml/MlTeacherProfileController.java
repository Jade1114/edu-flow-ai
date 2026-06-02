package com.yuy.eduflow.ml;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuy.eduflow.common.ApiResponse;
import com.yuy.eduflow.common.exception.ResourceNotFoundException;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.Map;
import java.util.stream.Stream;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ml/teacher-profiles")
public class MlTeacherProfileController {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @GetMapping("/v3")
    public ApiResponse<Map<String, Object>> getV3Profiles() {
        return ApiResponse.success(readJsonFile(
            "data/profiles/v3/teacher_profiles_v3.json",
            "V3 教师画像文件不存在，请先运行画像生成脚本",
            "读取 V3 教师画像文件失败"
        ));
    }

    @GetMapping("/v3/satisfaction/latest")
    public ApiResponse<Map<String, Object>> getLatestV3SatisfactionReport() {
        Path path = latestSatisfactionReportPath();
        return ApiResponse.success(readJsonFile(path, "读取 V3 教师画像满足度报告失败"));
    }

    private Path latestSatisfactionReportPath() {
        Path dir = resolveProjectRoot().resolve("data/profiles/v3");
        if (!Files.exists(dir)) {
            throw new ResourceNotFoundException("V3 教师画像满足度报告不存在，请先运行课表满足度分析脚本");
        }
        try (Stream<Path> stream = Files.list(dir)) {
            return stream
                .filter(path -> path.getFileName().toString().endsWith("_teacher_satisfaction_report.json"))
                .max(Comparator.comparingLong(path -> path.toFile().lastModified()))
                .orElseThrow(() -> new ResourceNotFoundException("V3 教师画像满足度报告不存在，请先运行课表满足度分析脚本"));
        } catch (IOException e) {
            throw new IllegalStateException("查找 V3 教师画像满足度报告失败: " + e.getMessage(), e);
        }
    }

    private Map<String, Object> readJsonFile(String relativePath, String notFoundMessage, String readErrorMessage) {
        Path path = resolveProjectRoot().resolve(relativePath);
        if (!Files.exists(path)) {
            throw new ResourceNotFoundException(notFoundMessage);
        }
        return readJsonFile(path, readErrorMessage);
    }

    private Map<String, Object> readJsonFile(Path path, String readErrorMessage) {
        try {
            return objectMapper.readValue(path.toFile(), new TypeReference<>() {});
        } catch (IOException e) {
            throw new IllegalStateException(readErrorMessage + ": " + e.getMessage(), e);
        }
    }

    private Path resolveProjectRoot() {
        Path current = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        if (current.getFileName() != null && "server".equals(current.getFileName().toString())) {
            return current.getParent();
        }
        return current;
    }
}
