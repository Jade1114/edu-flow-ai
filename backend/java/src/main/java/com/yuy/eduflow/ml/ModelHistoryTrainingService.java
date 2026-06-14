package com.yuy.eduflow.ml;

import com.yuy.eduflow.common.exception.BusinessException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Service
public class ModelHistoryTrainingService {
    private static final Logger log = LoggerFactory.getLogger(ModelHistoryTrainingService.class);
    private static final DateTimeFormatter FILE_TIME_FORMAT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    private static final long SSE_TIMEOUT_MS = 700_000L;

    private final MlFeedbackTrainingMapper mapper;
    private final ExecutorService trainingExecutor = Executors.newCachedThreadPool();

    public ModelHistoryTrainingService(MlFeedbackTrainingMapper mapper) {
        this.mapper = mapper;
    }

    public Map<String, Object> trainFromHistory(String rawDir) {
        return runHistoryTraining(rawDir, line -> {});
    }

    public SseEmitter streamTrainFromHistory(String rawDir) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        sendSse(emitter, "log", "准备启动历史数据训练：" + rawDir);

        CompletableFuture.runAsync(() -> {
            try {
                Map<String, Object> result = runHistoryTraining(rawDir, line -> sendSse(emitter, "log", line));
                sendSse(emitter, "done", result);
                emitter.complete();
            } catch (Exception e) {
                log.warn("History training stream failed: {}", e.getMessage(), e);
                sendSse(emitter, "failed", Map.of("message", e.getMessage()));
                emitter.completeWithError(e);
            }
        }, trainingExecutor);

        return emitter;
    }

    private Map<String, Object> runHistoryTraining(String rawDir, Consumer<String> outputConsumer) {
        Path rawDirPath = resolveRawDir(rawDir);
        List<String> command = new ArrayList<>();
        command.add(resolvePython().toString());
        command.add("v3.5/train_from_history.py");
        command.add("--raw-dir");
        command.add(rawDirPath.toAbsolutePath().toString());
        command.add("--record-db");

        log.info("Starting history training: {}", String.join(" ", command));
        outputConsumer.accept("启动命令：" + String.join(" ", command));

        Path pythonRoot = resolvePythonRoot();
        MlTrainingLog trainingLog = createLog(rawDir);
        mapper.insertTrainingLog(trainingLog);

        Process process = null;
        StringBuilder output = new StringBuilder();
        try {
            process = new ProcessBuilder(command)
                .directory(pythonRoot.toFile())
                .redirectErrorStream(true)
                .start();

            Process runningProcess = process;
            CompletableFuture<Void> outputReader = CompletableFuture.runAsync(() -> readProcessOutput(runningProcess, output, outputConsumer), trainingExecutor);
            boolean finished = process.waitFor(600, TimeUnit.SECONDS);

            if (!finished) {
                process.destroyForcibly();
                updateLog(trainingLog, "FAILED", null, "训练超时");
                outputConsumer.accept("训练超时，已强制终止");
                throw new BusinessException(500, "训练超时");
            }

            outputReader.get(5, TimeUnit.SECONDS);

            if (process.exitValue() != 0) {
                updateLog(trainingLog, "FAILED", null, "训练异常: " + output);
                outputConsumer.accept("训练进程异常退出，exitCode=" + process.exitValue());
                throw new BusinessException(500, "训练异常");
            }

            Map<String, Object> result = parseOutput(output.toString());
            updateLog(trainingLog, "SUCCEEDED", extractSampleCount(result), null);
            log.info("History training done: {} samples", extractSampleCount(result));
            outputConsumer.accept("历史训练完成，样本数：" + (extractSampleCount(result) == null ? "未知" : extractSampleCount(result)));
            return result;
        } catch (IOException e) {
            updateLog(trainingLog, "FAILED", null, "启动训练失败: " + e.getMessage());
            outputConsumer.accept("启动训练失败：" + e.getMessage());
            throw new BusinessException(500, "启动训练失败");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            updateLog(trainingLog, "FAILED", null, "训练被中断");
            outputConsumer.accept("训练被中断");
            throw new BusinessException(500, "训练被中断");
        } catch (Exception e) {
            updateLog(trainingLog, "FAILED", null, "训练失败: " + e.getMessage());
            outputConsumer.accept("训练失败：" + e.getMessage());
            if (e instanceof BusinessException businessException) {
                throw businessException;
            }
            throw new BusinessException(500, "训练失败");
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
            }
        }
    }

    private void readProcessOutput(Process process, StringBuilder output, Consumer<String> outputConsumer) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                synchronized (output) {
                    output.append(line).append(System.lineSeparator());
                }
                log.info("[history-training] {}", line);
                outputConsumer.accept(line);
            }
        } catch (IOException e) {
            log.warn("Failed to read history training output: {}", e.getMessage());
            outputConsumer.accept("读取训练日志失败：" + e.getMessage());
        }
    }

    private void sendSse(SseEmitter emitter, String eventName, Object data) {
        try {
            emitter.send(SseEmitter.event().name(eventName).data(data));
        } catch (IOException e) {
            log.warn("Failed to send history training SSE event: {}", e.getMessage());
        }
    }

    private MlTrainingLog createLog(String rawDir) {
        MlTrainingLog logEntry = new MlTrainingLog();
        logEntry.setTrainingType("HISTORY");
        logEntry.setModelVersion("v3.5-history");
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

    private Path resolveRawDir(String rawDir) {
        Path userDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        for (int level = 0; level <= 3; level++) {
            Path base = userDir;
            for (int up = 0; up < level; up++) {
                base = base.getParent();
                if (base == null) break;
            }
            if (base == null) continue;
            Path resolved = base.resolve(rawDir).normalize();
            if (resolved.toFile().exists() && resolved.toFile().isDirectory()) {
                return resolved;
            }
        }
        Path asIs = Paths.get(rawDir).normalize();
        if (asIs.toFile().exists() && asIs.toFile().isDirectory()) {
            return asIs;
        }
        throw new ValidationException("原始课表目录不存在: " + rawDir + " (已尝试 5 种路径组合)");
    }

    private Path resolvePython() {
        Path userDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        for (int level = 0; level <= 3; level++) {
            Path base = userDir;
            for (int up = 0; up < level; up++) {
                base = base.getParent();
                if (base == null) break;
            }
            if (base == null) continue;
            Path python = base.resolve("python/.venv/bin/python").normalize();
            if (python.toFile().exists()) return python;
        }
        return Paths.get("python3");
    }

    private Path resolvePythonRoot() {
        Path userDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        for (int level = 0; level <= 3; level++) {
            Path base = userDir;
            for (int up = 0; up < level; up++) {
                base = base.getParent();
                if (base == null) break;
            }
            if (base == null) continue;
            Path python = base.resolve("python").normalize();
            if (python.toFile().exists() && python.toFile().isDirectory()) return python;
        }
        Path fallback = Paths.get("python");
        if (fallback.toFile().exists()) return fallback;
        return userDir.resolve("python");
    }
}
