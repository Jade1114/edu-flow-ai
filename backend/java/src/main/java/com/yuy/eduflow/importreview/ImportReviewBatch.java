package com.yuy.eduflow.importreview;

import lombok.Data;

@Data
public class ImportReviewBatch {
    private String id;
    private String name;
    private String path;
    private int reviewItemCount;
    private int pendingCount;
    private int conflictCount;
    private int newItemCount;
    private boolean hasReviewFile;
}
