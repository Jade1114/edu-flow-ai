package com.yuy.eduflow.importreview;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class ImportReviewService {
    private static final String REVIEW_FILE = "import_review_items.csv";
    private static final List<String> HEADERS = List.of(
        "review_id", "review_type", "entity_type", "entity_key", "display_name",
        "field_name", "field_label", "db_id", "db_value", "import_value",
        "status", "decision", "allowed_decisions", "recommended_decision", "reason", "review_note"
    );

    private final Path rootDir;

    public ImportReviewService() {
        this.rootDir = resolveRootDir();
    }

    public List<ImportReviewBatch> findBatches() {
        if (!Files.exists(rootDir)) return List.of();
        try (var stream = Files.list(rootDir)) {
            return stream
                .filter(Files::isDirectory)
                .sorted()
                .map(this::toBatch)
                .toList();
        } catch (IOException e) {
            throw new ValidationException("读取导入审核批次失败");
        }
    }

    public List<ImportReviewItem> findItems(String batchId) {
        Path file = reviewFile(batchId);
        if (!Files.exists(file)) {
            throw new ResourceNotFoundException("导入审核清单不存在");
        }
        return readItems(file);
    }

    public Map<String, Object> saveItems(String batchId, ImportReviewSaveRequest request) {
        if (request == null || request.items() == null) {
            throw new ValidationException("审核项不能为空");
        }
        Path file = reviewFile(batchId);
        if (!Files.exists(file)) {
            throw new ResourceNotFoundException("导入审核清单不存在");
        }
        writeItems(file, request.items());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("batchId", batchId);
        result.put("count", request.items().size());
        result.put("path", file.toString());
        return result;
    }

    private ImportReviewBatch toBatch(Path dir) {
        ImportReviewBatch batch = new ImportReviewBatch();
        batch.setId(dir.getFileName().toString());
        batch.setName(dir.getFileName().toString());
        batch.setPath(dir.toString());
        Path file = dir.resolve(REVIEW_FILE);
        batch.setHasReviewFile(Files.exists(file));
        if (Files.exists(file)) {
            List<ImportReviewItem> items = readItems(file);
            batch.setReviewItemCount(items.size());
            batch.setPendingCount((int) items.stream().filter(item -> item.getDecision() == null || item.getDecision().isBlank()).count());
            batch.setConflictCount((int) items.stream().filter(item -> "conflict".equals(item.getReviewType())).count());
            batch.setNewItemCount((int) items.stream().filter(item -> "new_item".equals(item.getReviewType())).count());
        }
        return batch;
    }

    private Path reviewFile(String batchId) {
        Path dir = rootDir.resolve(safeBatchId(batchId)).normalize();
        if (!dir.startsWith(rootDir)) {
            throw new ValidationException("非法批次路径");
        }
        return dir.resolve(REVIEW_FILE);
    }

    private String safeBatchId(String batchId) {
        if (batchId == null || batchId.isBlank() || batchId.contains("/") || batchId.contains("\\") || batchId.contains("..")) {
            throw new ValidationException("非法批次 ID");
        }
        return batchId;
    }

    private List<ImportReviewItem> readItems(Path file) {
        try {
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            if (!lines.isEmpty() && lines.get(0).startsWith("\uFEFF")) {
                lines.set(0, lines.get(0).substring(1));
            }
            if (lines.isEmpty()) return List.of();
            List<String> headers = parseCsvLine(lines.get(0));
            List<ImportReviewItem> items = new ArrayList<>();
            for (int i = 1; i < lines.size(); i++) {
                if (lines.get(i).isBlank()) continue;
                List<String> values = parseCsvLine(lines.get(i));
                Map<String, String> row = new LinkedHashMap<>();
                for (int index = 0; index < headers.size(); index++) {
                    row.put(headers.get(index), index < values.size() ? values.get(index) : "");
                }
                items.add(toItem(row));
            }
            return items;
        } catch (IOException e) {
            throw new ValidationException("读取导入审核清单失败");
        }
    }

    private void writeItems(Path file, List<ImportReviewItem> items) {
        List<String> lines = new ArrayList<>();
        lines.add(toCsvLine(HEADERS));
        for (ImportReviewItem item : items) {
            lines.add(toCsvLine(List.of(
                value(item.getReviewId()), value(item.getReviewType()), value(item.getEntityType()), value(item.getEntityKey()),
                value(item.getDisplayName()), value(item.getFieldName()), value(item.getFieldLabel()), value(item.getDbId()),
                value(item.getDbValue()), value(item.getImportValue()), value(item.getStatus()), value(item.getDecision()),
                value(item.getAllowedDecisions()), value(item.getRecommendedDecision()), value(item.getReason()), value(item.getReviewNote())
            )));
        }
        try {
            Files.write(file, lines, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new ValidationException("保存导入审核清单失败");
        }
    }

    private ImportReviewItem toItem(Map<String, String> row) {
        ImportReviewItem item = new ImportReviewItem();
        item.setReviewId(row.getOrDefault("review_id", ""));
        item.setReviewType(row.getOrDefault("review_type", ""));
        item.setEntityType(row.getOrDefault("entity_type", ""));
        item.setEntityKey(row.getOrDefault("entity_key", ""));
        item.setDisplayName(row.getOrDefault("display_name", ""));
        item.setFieldName(row.getOrDefault("field_name", ""));
        item.setFieldLabel(row.getOrDefault("field_label", ""));
        item.setDbId(row.getOrDefault("db_id", ""));
        item.setDbValue(row.getOrDefault("db_value", ""));
        item.setImportValue(row.getOrDefault("import_value", ""));
        item.setStatus(row.getOrDefault("status", ""));
        item.setDecision(row.getOrDefault("decision", ""));
        item.setAllowedDecisions(row.getOrDefault("allowed_decisions", ""));
        item.setRecommendedDecision(row.getOrDefault("recommended_decision", ""));
        item.setReason(row.getOrDefault("reason", ""));
        item.setReviewNote(row.getOrDefault("review_note", ""));
        return item;
    }

    private List<String> parseCsvLine(String line) {
        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (ch == ',' && !quoted) {
                result.add(current.toString());
                current.setLength(0);
            } else {
                current.append(ch);
            }
        }
        result.add(current.toString());
        return result;
    }

    private String toCsvLine(List<String> values) {
        return values.stream().map(this::escapeCsv).reduce((a, b) -> a + "," + b).orElse("");
    }

    private String escapeCsv(String value) {
        String text = value(value);
        if (text.contains(",") || text.contains("\"") || text.contains("\n") || text.contains("\r")) {
            return "\"" + text.replace("\"", "\"\"") + "\"";
        }
        return text;
    }

    private String value(String value) {
        return value == null ? "" : value;
    }

    private Path resolveRootDir() {
        Path userDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        if (userDir.endsWith(Paths.get("backend", "java"))) {
            return userDir.getParent().resolve("data/parsed/schedule_imports").normalize();
        }
        return userDir.resolve("backend/data/parsed/schedule_imports").normalize();
    }
}
