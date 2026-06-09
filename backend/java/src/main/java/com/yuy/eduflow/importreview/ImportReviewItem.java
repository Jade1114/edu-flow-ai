package com.yuy.eduflow.importreview;

import lombok.Data;

@Data
public class ImportReviewItem {
    private String reviewId;
    private String reviewType;
    private String entityType;
    private String entityKey;
    private String displayName;
    private String fieldName;
    private String fieldLabel;
    private String dbId;
    private String dbValue;
    private String importValue;
    private String status;
    private String decision;
    private String allowedDecisions;
    private String recommendedDecision;
    private String reason;
    private String reviewNote;
}
