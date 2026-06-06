package com.yuy.eduflow.enums;

import com.yuy.eduflow.common.exception.ValidationException;

public enum AdjustmentStatus implements CodeEnum {
    PENDING("PENDING", "待处理"),
    APPROVED("APPROVED", "已通过"),
    REJECTED("REJECTED", "已拒绝");

    private final String code;
    private final String label;

    AdjustmentStatus(String code, String label) {
        this.code = code;
        this.label = label;
    }

    @Override
    public String code() { return code; }

    @Override
    public String label() { return label; }

    public static AdjustmentStatus from(String code) {
        if (code == null || code.isBlank()) return null;
        for (AdjustmentStatus s : values()) {
            if (s.code.equalsIgnoreCase(code.trim())) return s;
        }
        throw new ValidationException("未知调课状态: " + code);
    }
}
