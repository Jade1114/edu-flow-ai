package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class ModelHistoryTrainingService {
    private static final Logger log = LoggerFactory.getLogger(ModelHistoryTrainingService.class);
    private static final DateTimeFormatter FILE_TIME_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    private final MlFeedbackTrainingMapper mapper;

    public ModelHistoryTrainingService(MlFeedbackTrainingMapper mapper) {
        this.mapper = mapper;
    }

    public Map<String, Object> trainFromHistory(String rawDir) {
        Path rawDirPath = Paths.get(rawDir);
        if (!rawDirPath.toFile().exists() || !rawDirPath.toFile().isDirectory()) {
            throw new ValidationException("原始课表目录不存在: " + rawDir);
        }
        List<String> command = new ArrayList<>();
        command.add(resolvePython().toString());
        command.add("v3.5/train_from_history.py");
        command.add("--raw-dir");
        command.add(rawDirPath.toAbsolutePath().toString());
        command.add("--record-db");

        log.info("Starting history training: {}", String.join(" ", command));

        Path pythonRoot = resolvePythonRoot();
        MlTrainingLog trainingLog = createLog(rawDir);
        mapper.insertTrainingLog(trainingLog);

        try {
            Process process = new ProcessBuilder(command)
                .directory(pythonRoot.toFile())
                .redirectErrorStream(true)
                .start();
            boolean finished = process.waitFor(600, TimeUnit.SECONDS);
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);

            if (!finished) {
                process.destroyForcibly();
                updateLog(trainingLog, "FAILED", null, "训练超时");
                throw new BusinessException(500, "训练超时");
            }
            if (process.exitValue() != 0) {
                updateLog(trainingLog, "FAILED", null, "训练异常: " + output);
                throw new BusinessException(500, "训练异常");
            }

            Map<String, Object> result = parseOutput(output);
            updateLog(trainingLog, "SUCCEEDED", extractSampleCount(result), null);
            log.info("History training done: {} samples", extractSampleCount(result));
            return result;
        } catch (IOException e) {
            updateLog(trainingLog, "FAILED", null, "启动训练失败: " + e.getMessage());
            throw new BusinessException(500, "启动训练失败");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            updateLog(trainingLog, "FAILED", null, "训练被中断");
            throw new BusinessException(500, "训练被中断");
        }
    }

    private MlTrainingLog createLog(String rawDir) {
        MlTrainingLog logEntry = new MlTrainingLog();
        logEntry.setTrainingType("HISTORY");
        logEntry.setStatus("RUNNING");
        logEntry.setErrorMessage("Training from history: " + rawDir);
        logEntry.setTrainStartedAt(LocalDateTime.now());
        return logEntry;
    }

    private void updateLog(MlTrainingLog logEntry, String status, Integer sampleCount, String errorMessage) {
        try {
            logEntry.setStatus(status);
            if (sampleCount != null) {
                logEntry.setSampleCount(sampleCount);
                logEntry.setPositiveCount(sampleCount);
                logEntry.setNegativeCount(0);
            }
            logEntry.setErrorMessage(errorMessage);
            logEntry.setTrainFinishedAt(LocalDateTime.now());
            mapper.updateTrainingLog(logEntry);
        } catch (Exception e) {
            log.warn("Failed to update training log: {}", e.getMessage());
        }
    }

    private Integer extractSampleCount(Map<String, Object> result) {
        if (result == null) return null;
        try {
            var extract = (Map<String, Object>) result.get("extract_result");
            if (extract != null && extract.get("total_samples") instanceof Number n) {
                return n.intValue();
            }
        } catch (Exception ignored) {}
        return null;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseOutput(String output) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("rawOutput", output);
        result.put("command", "train_from_history.py");
        try {
            int jsonStart = output.indexOf('{');
            if (jsonStart >= 0) {
                String json = output.substring(jsonStart);
                var parsed = new com.fasterxml.jackson.databind.ObjectMapper().readValue(json, Map.class);
                result.putAll(parsed);
            }
        } catch (Exception e) {
            log.warn("Failed to parse training output: {}", e.getMessage());
        }
        return result;
    }

    private Path resolvePython() {
        Path python = resolvePythonRoot().resolve(".venv/bin/python");
        if (python.toFile().exists()) return python;
        return Paths.get("python3");
    }

    private Path resolvePythonRoot() {
        Path userDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        if (userDir.endsWith(Paths.get("backend", "java"))) {
            return userDir.getParent().resolve("python").normalize();
        }
        return userDir.resolve("backend/python").normalize();
    }
}
