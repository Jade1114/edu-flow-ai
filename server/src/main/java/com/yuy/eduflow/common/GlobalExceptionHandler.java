package com.yuy.eduflow.common;

import com.yuy.eduflow.common.exception.BusinessException;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    // --- 自定义业务异常：从 BusinessException 中读取 httpStatus ---
    @ExceptionHandler(BusinessException.class)
    public ApiResponse<Void> handleBusinessException(BusinessException exception, HttpServletResponse response) {
        prepareJsonResponse(response);
        return ApiResponse.error(exception.getHttpStatus(), exception.getMessage());
    }

    // --- @Valid 校验失败 ---
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleValidationException(MethodArgumentNotValidException exception) {
        String message = exception.getBindingResult().getFieldErrors().stream()
            .findFirst()
            .map(error -> error.getField() + " " + error.getDefaultMessage())
            .orElse("参数错误");
        return ApiResponse.error(400, message);
    }

    // --- 请求参数缺失 ---
    @ExceptionHandler(MissingServletRequestParameterException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMissingParam(MissingServletRequestParameterException exception) {
        return ApiResponse.error(400, "缺少请求参数: " + exception.getParameterName());
    }

    // --- 请求体 JSON 解析失败 ---
    @ExceptionHandler(HttpMessageNotReadableException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMessageNotReadable(HttpMessageNotReadableException exception) {
        return ApiResponse.error(400, "请求体格式错误");
    }

    // --- 路径参数类型不匹配（如 /api/xxx/abc 但期望 Long） ---
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleTypeMismatch(MethodArgumentTypeMismatchException exception) {
        return ApiResponse.error(400, "参数类型错误: " + exception.getName());
    }

    // --- JDK 原生 IllegalArgumentException（兼容旧代码） ---
    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleIllegalArgumentException(IllegalArgumentException exception) {
        return ApiResponse.error(400, exception.getMessage());
    }

    // --- JDK 原生 IllegalStateException ---
    @ExceptionHandler(IllegalStateException.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleIllegalStateException(IllegalStateException exception) {
        return ApiResponse.error(500, "服务器状态异常");
    }

    // --- 兜底：所有未捕获异常 ---
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleException(Exception exception, HttpServletResponse response) {
        prepareJsonResponse(response);
        // 不把内部异常信息暴露给前端
        return ApiResponse.error(500, "服务器内部错误");
    }

    private void prepareJsonResponse(HttpServletResponse response) {
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
    }
}
