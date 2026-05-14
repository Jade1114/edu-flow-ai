package com.yuy.eduflow.common;

import com.yuy.eduflow.common.exception.ResourceNotFoundException;
import com.yuy.eduflow.common.exception.ValidationException;

/**
 * 参数/状态断言工具，替代直接 throw IllegalArgumentException。
 */
public final class Assert {

    private Assert() {}

    // --- Validation (400) ---

    public static void notNull(Object obj, String message) {
        if (obj == null) throw new ValidationException(message);
    }

    public static void hasText(String str, String message) {
        if (str == null || str.isBlank()) throw new ValidationException(message);
    }

    public static void isTrue(boolean condition, String message) {
        if (!condition) throw new ValidationException(message);
    }

    public static void positive(Long value, String entityName) {
        if (value == null) throw new ValidationException(entityName + "不能为空");
        if (value <= 0) throw new ValidationException(entityName + "必须大于0");
    }

    public static void positiveId(Long id, String entityName) {
        positive(id, entityName);
    }

    // --- Not Found (404) ---

    public static void notFound(boolean condition, String message) {
        if (!condition) throw new ResourceNotFoundException(message);
    }
}
