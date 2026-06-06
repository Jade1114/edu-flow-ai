package com.yuy.eduflow.common.exception;

public class ResourceNotFoundException extends BusinessException {
    public ResourceNotFoundException(String message) {
        super(404, message);
    }
}
