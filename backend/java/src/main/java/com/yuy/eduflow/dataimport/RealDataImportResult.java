package com.yuy.eduflow.dataimport;

public record RealDataImportResult(
    boolean success,
    int exitCode,
    String command,
    String output,
    String error
) {
}
