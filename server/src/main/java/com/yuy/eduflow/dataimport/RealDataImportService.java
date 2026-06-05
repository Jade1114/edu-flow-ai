package com.yuy.eduflow.dataimport;

import com.yuy.eduflow.common.exception.BusinessException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.springframework.stereotype.Service;

@Service
public class RealDataImportService {
    private static final Duration IMPORT_TIMEOUT = Duration.ofMinutes(5);
    private static final int MAX_OUTPUT_LENGTH = 20000;

    public RealDataImportResult importCleanDataset() {
        Path projectRoot = resolveProjectRoot();
        Path script = projectRoot.resolve("scripts/import_clean_to_db.py");
        if (!Files.exists(script)) {
            throw new BusinessException(500, "真实数据导入脚本不存在：" + script);
        }
        Path dataDir = projectRoot.resolve("data/real-dataset");
        validateRequiredDataFiles(dataDir);

        List<String> command = List.of("python3", script.toString());
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(projectRoot.toFile());
        builder.redirectErrorStream(true);
        Map<String, String> env = builder.environment();
        env.putIfAbsent("PYTHONPATH", projectRoot.toString());

        try {
            Process process = builder.start();
            boolean finished = process.waitFor(IMPORT_TIMEOUT.toSeconds(), TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new BusinessException(500, "真实数据导入超时，请检查脚本或数据库连接");
            }
            String output = truncate(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
            int exitCode = process.exitValue();
            if (exitCode != 0) {
                throw new BusinessException(500, "真实数据导入失败：" + output);
            }
            return new RealDataImportResult(true, exitCode, String.join(" ", command), output, "");
        } catch (IOException exception) {
            throw new BusinessException(500, "启动真实数据导入脚本失败：" + exception.getMessage(), exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new BusinessException(500, "真实数据导入被中断", exception);
        }
    }

    private Path resolveProjectRoot() {
        Path current = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        if (Files.exists(current.resolve("scripts/import_clean_to_db.py"))) {
            return current;
        }
        Path parent = current.getParent();
        if (parent != null && Files.exists(parent.resolve("scripts/import_clean_to_db.py"))) {
            return parent;
        }
        return current;
    }

    private void validateRequiredDataFiles(Path dataDir) {
        List<String> required = List.of(
            "teachers.jsonl",
            "courses_clean.jsonl",
            "class_groups.jsonl",
            "classrooms_clean.jsonl",
            "teaching_tasks_clean.jsonl"
        );
        for (String file : required) {
            Path path = dataDir.resolve(file);
            if (!Files.exists(path)) {
                throw new BusinessException(400, "缺少真实数据文件：" + path);
            }
        }
    }

    private String truncate(String value) {
        if (value == null || value.length() <= MAX_OUTPUT_LENGTH) {
            return value;
        }
        return value.substring(0, MAX_OUTPUT_LENGTH) + "\n...输出过长，已截断";
    }
}
