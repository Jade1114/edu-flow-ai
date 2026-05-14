package com.yuy.eduflow.common.exception;

/**
 * 自定义业务异常基类，统一携带 HTTP status code。
 */
public class BusinessException extends RuntimeException {
    private final int httpStatus;

    public BusinessException(int httpStatus, String message) {
        super(message);
        this.httpStatus = httpStatus;
    }

    public BusinessException(int httpStatus, String message, Throwable cause) {
        super(message, cause);
        this.httpStatus = httpStatus;
    }

    public int getHttpStatus() {
        return httpStatus;
    }
}
