# Edu Flow AI 前端 MVP

基于 Vue 3 + Element Plus 的智能教务管理系统前端。

## 技术栈

- Vue 3 (Composition API)
- Vue Router 4
- Pinia
- Element Plus
- Axios
- Vite

## 页面结构

| 路由 | 页面 | 说明 |
|------|------|------|
| `/login` | 登录页 | 工号密码登录，区分教务/教师角色 |
| `/admin` | 教务端首页 | 管理员 Dashboard |
| `/admin/basic-data` | 基础数据管理 | 教师 / 课程 / 班级 / 教室 CRUD |
| `/admin/allocation` | 分课任务 | 创建任务、AI 生成候选方案、确认方案 |
| `/admin/timetable` | 课表查询 | 正式课表多条件筛选查询 |
| `/admin/adjustment` | 调课处理 | 查看申请、AI 生成建议、确认/拒绝 |
| `/teacher` | 教师端首页 | 教师 Dashboard |
| `/teacher/timetable` | 我的课表 | 教师个人课表查询 |
| `/teacher/profile` | 个人信息 | 教师画像填写（技能、时间偏好等） |
| `/teacher/adjustment` | 调课申请 | 提交调课申请、查看历史 |
| `/debug` | 接口调试页 | 保留的原调试页面 |

## 启动

确保后端已启动（默认 `http://localhost:8080`）：

```bash
cd server
./mvnw spring-boot:run
```

启动前端 dev server：

```bash
cd web
pnpm dev
```

打开浏览器访问 Vite 输出的地址，通常是 `http://localhost:5173`。

`vite.config.js` 已将 `/api` 代理到 `http://localhost:8080`，前端请求直接写 `/api/xxx` 即可。

## 测试账号

| 账号 | 密码 | 角色 |
|------|------|------|
| ADMIN001 | 123456 | 教务管理员 |
| T1001 | 123456 | 教师 |
| T1002 ~ T1009 | 123456 | 教师 |

## 构建

```bash
cd web
pnpm run build
```

构建产物输出到 `dist/` 目录。

## 后端接口

后端已提供完整 REST API，响应格式统一为：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

主要接口前缀均为 `/api`：

- `POST /api/auth/login` — 登录
- `GET/POST/PUT/DELETE /api/teachers` — 教师管理
- `GET/PUT /api/teachers/{id}/profile` — 教师画像
- `GET/POST/PUT/DELETE /api/courses` — 课程管理
- `GET/POST/PUT/DELETE /api/class-groups` — 班级管理
- `GET/POST/PUT/DELETE /api/classrooms` — 教室管理
- `GET/POST /api/allocation-tasks` — 分课任务
- `POST /api/allocation-tasks/{id}/schemes` — AI 生成候选方案
- `GET /api/allocation-tasks/{id}/schemes` — 查询任务候选方案
- `POST /api/allocation-schemes/{id}/confirm` — 确认候选方案
- `GET /api/course-assignments` — 正式课表查询
- `GET /api/teachers/{id}/course-assignments` — 教师课表
- `GET/POST /api/adjustment-requests` — 调课申请
- `POST /api/adjustment-requests/{id}/suggestions` — AI 调课建议
- `POST /api/adjustment-requests/{id}/confirm` — 确认调课
- `POST /api/adjustment-requests/{id}/reject` — 拒绝调课

MVP 阶段登录使用明文密码校验，不发 token，前端通过 localStorage 保存用户信息和角色进行路由守卫。
