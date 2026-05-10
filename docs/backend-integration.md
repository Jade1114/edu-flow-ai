# 后端联调流程

## 启动数据

1. 使用 `server/src/main/resources/db/schema.sql` 初始化数据库。
2. 使用 `server/src/main/resources/db/seed-basic.sql` 导入演示数据。
3. 演示账号示例：`ADMIN001`、`T1001`，演示密码为 `123456`。

这些密码仅用于演示项目联调，不是真实密码。

## 启动后端

```bash
cd server
mvn spring-boot:run
```

默认地址：

```text
http://localhost:8080
```

## 登录步骤

先调用简化登录接口：

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"employeeNo":"ADMIN001","password":"123456"}'
```

成功后会返回 `id`、`employeeNo`、`name`、`displayName`、`role`、`teacherId`、`department`、`title`。MVP 不返回 token，不创建 session，后续接口也不做登录态拦截。

## 查看页联调

```bash
cd web
npm run dev
```

打开 Vite 输出地址后，在“登录测试”区域输入工号和密码调用 `POST /api/auth/login`，再继续调用分课、课表、调课等接口。
