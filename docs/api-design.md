# API 设计

## MVP 简化登录

状态：已实现。

`POST /api/auth/login`

请求体：

```json
{
  "employeeNo": "T1001",
  "password": "123456"
}
```

兼容字段：`username` 可作为 `employeeNo` 使用。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 2,
    "employeeNo": "T1001",
    "name": "张明",
    "displayName": "张明",
    "role": "TEACHER",
    "teacherId": 2,
    "department": "软件工程系",
    "title": "副教授"
  }
}
```

失败响应：返回 HTTP 400，`message` 为中文错误信息，例如 `工号不存在`、`密码错误`、`账号状态非 ACTIVE，禁止登录`。

说明：MVP 直接在 `teacher` 表上增加 `employee_no`、`password`、`role` 字段，不单独建 `user` 表，不接 Spring Security，不发 token，不做 session。当前密码为明文演示数据，仅用于本地联调和演示；后续可替换为 Spring Security、独立用户表和密码哈希。
