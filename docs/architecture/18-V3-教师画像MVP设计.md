# V3 — 教师画像 MVP 设计与实现

> 状态：✅ MVP 已实现  
> 更新时间：2026-06-02  
> 定位：教师画像先作为**可量化、可解释、可分析的知识层**，暂不直接影响 CP-SAT 排课结果。

---

## 一句话定义

> **V3 教师画像不是 V1 penalty 的迁移，而是从真实课表中提取教师行为模式，形成结构化画像，并对生成课表做教师偏好满足度分析。**

---

## 为什么不是直接迁移 V1

V1 的教师画像主要服务于 GA fitness：

```text
候选方案 → profile_penalty → GA 排序
```

V3 的主链路是：

```text
Placement Model → Task Plans → CP-SAT 全局方案选择
```

因此教师画像应先独立成为知识资产：

```text
真实课表 / 教师备注 / 调课反馈
  ↓
结构化教师画像
  ↓
课表满足度分析 / 解释 / 报表
  ↓
后续再进入 CP-SAT 软目标和 Placement Model 特征
```

---

## 当前 MVP 范围

### 已实现

| 功能 | 说明 |
|------|------|
| 历史课表画像提取 | 从 `timetables_clean.jsonl` + `teaching_tasks_clean.jsonl` 按教师聚合行为模式 |
| 结构化画像输出 | 输出 `teacher_profiles_v3.json` |
| 后端读取接口 | `GET /api/ml/teacher-profiles/v3` 读取画像 JSON，并合并教师声明画像 |
| 方案满足度接口 | `GET /api/ml/teacher-profiles/v3/satisfaction?schemeId={id}` 按方案实时分析 |
| 教师声明画像合并 | 合并 `teacher_profile.profile_preference_json`，教师声明优先于历史推断 |
| 前端画像页面 | `/admin/teacher-profiles` 可视化每位教师画像 |
| 课表满足度分析 | 用生成的 `schemes.jsonl` 或 Java 方案明细对比画像，输出每位教师满足度 |
| 全校汇总报告 | 平均满足度、低满足教师数量、Top10 低满足教师 |
| 独立 CLI | 不影响 V3 pipeline / CP-SAT |

### 暂未实现

| 功能 | 原因 |
|------|------|
| CP-SAT 软目标接入 | 先分析后影响，避免破坏当前可运行主链路 |
| Placement Model 特征增强 | 需要重训模型，放到 Phase 3 |
| 教师声明画像合并 | Java 已有基础设施，但本 MVP 先做数据画像 |
| 调课说明 LLM 分类 | 需要反馈事件数据沉淀后再接 |
| 向量证据库 | 作为未来证据层，不是画像主干 |

---

## 画像字段

每位教师输出三层内容：

```json
{
  "teacher_id": 252,
  "teacher_name": "张老师",
  "source": "derived_from_real_timetable",
  "observation_count": 128,
  "derived_from_data": {
    "early_period_rate": 0.0312,
    "late_period_rate": 0.1094,
    "weekday_rates": {"1": 0.18, "2": 0.24},
    "period_rates": {"1": 0.03, "2": 0.31},
    "preferred_weekdays": [2, 4],
    "common_periods": [2, 3],
    "avg_daily_lessons": 2.4,
    "max_observed_daily_lessons": 5,
    "p90_daily_lessons": 4,
    "avg_weekly_active_days": 2.6,
    "compactness_score": 0.65,
    "room_type_rates": {"普通教室": 0.8},
    "common_room_types": ["普通教室"]
  },
  "final_profile": {
    "avoid_early_period": true,
    "avoid_late_period": false,
    "prefer_compact_schedule": false,
    "preferred_weekdays": [2, 4],
    "preferred_periods": [2, 3],
    "max_daily_lessons": 4,
    "preferred_room_types": ["普通教室"]
  }
}
```

`derived_from_data` 是统计事实，`final_profile` 是当前用于分析的结构化画像。

---

## 教师声明画像合并

后端读取画像时会实时合并 Java 侧已有的 `teacher_profile` 表：

```text
teacher_profiles_v3.json (历史统计画像)
  + teacher_profile.profile_preference_json (教师声明 / LLM 解析)
  ↓
final_profile (教师声明优先)
```

当前合并字段：

| Java LLM 字段 | V3 final_profile 字段 | 说明 |
|---------------|-----------------------|------|
| `avoidFirstPeriod` | `avoid_early_period` | 教师声明避开第 1 节则覆盖为 true |
| `avoidLastPeriod` | `avoid_late_period` | 教师声明避开晚课则覆盖为 true |
| `preferCompactSchedule` | `prefer_compact_schedule` | 教师声明偏好紧凑则覆盖为 true |
| `preferredWeekdays` | `preferred_weekdays` | 教师声明优先于历史常见星期 |
| `preferredMaxDailyHours` | `max_daily_lessons` | 教师声明优先于历史 p90 日课时 |
| `avoidSlots` | `declared_avoid_slots` | 当前仅展示/记录，后续进入硬确认或软约束 |

API 响应会额外包含：

```json
{
  "declared_profile_count": 12,
  "merge_strategy": "teacher_declared_overrides_derived_baseline"
}
```

每个教师若有声明画像，会出现：

```json
{
  "declared_profile": {
    "profile_note": "不太希望早八，课程尽量集中",
    "summary": "已解析教师排课偏好",
    "preference": {...}
  }
}
```

---

## 满足度分析口径

对每个教师的排课 item 计算 6 个组件：

| 组件 | 说明 |
|------|------|
| `early_period` | 如果画像显示避开第 1 节，则统计第 1 节出现比例 |
| `late_period` | 如果画像显示避开晚课，则统计晚课出现比例 |
| `preferred_weekday` | 排课是否落在历史偏好星期 |
| `preferred_period` | 排课是否落在历史常见节次 |
| `daily_load` | 单日课时是否超过画像中的 `max_daily_lessons` |
| `room_type` | 教室类型是否命中历史常用教室类型 |

当前总分为 6 个组件的平均值：

```text
satisfaction_score = mean(components)
```

这是 MVP 分析口径，后续可以改成可配置权重。

---

## CLI 使用

### 生成教师画像

```bash
python3 -m ml.scheduling_v3.teacher_profiles derive \
  --output data/profiles/v3/teacher_profiles_v3.json
```

示例结果：

```json
{"output": "data/profiles/v3/teacher_profiles_v3.json", "teacher_count": 517}
```

### 分析生成课表

```bash
python3 -m ml.scheduling_v3.teacher_profiles analyze \
  --schemes data/generated/v3/task_1_20260602185022985/schemes.jsonl \
  --profiles data/profiles/v3/teacher_profiles_v3.json \
  --output data/profiles/v3/task_1_teacher_satisfaction_report.json
```

示例汇总：

```json
{
  "avg_satisfaction_score": 0.7573,
  "teacher_count": 517,
  "low_satisfaction_count": 93,
  "hard_unavailable_violation_count": 0,
  "note": "MVP report covers derived soft preferences only; hard unavailable requires declared profile input."
}
```

---

## 前端可视化

管理端新增入口：

```text
/admin/teacher-profiles
```

页面能力：

- 顶部统计：画像教师数、教师声明画像数、低早课倾向人数、偏好紧凑排课人数、平均第 1 节占比、平均紧凑度
- 教师卡片：姓名、ID、历史样本数、第 1 节占比、紧凑度、常见星期、常见节次、画像标签、声明标记
- 搜索过滤：按教师姓名或 ID 搜索，并支持按声明状态、低满足状态、画像标签筛选
- 详情弹窗：最终画像、教师声明画像、星期分布、节次分布、日课时统计
- 课表满足度区块：平均满足度、覆盖教师数、低满足教师数、低满足 Top10
- 满足度详情弹窗：每位低满足教师的分项短板与证据统计
- 方案详情页：打开候选方案时同步展示该课表的教师画像满足度摘要与低满足 Top10

后端接口：

```text
GET /api/ml/teacher-profiles/v3
GET /api/ml/teacher-profiles/v3/satisfaction?schemeId={schemeId}
GET /api/ml/teacher-profiles/v3/satisfaction/latest
```

其中：

- `satisfaction?schemeId=`：方案详情页使用，按当前方案实时计算，避免串报告
- `satisfaction/latest`：教师画像总览页使用，读取最近生成的离线报告文件

---

## 输出文件

```text
data/profiles/v3/
├── teacher_profiles_v3.json                  # 画像基线
└── task_1_teacher_satisfaction_report.json    # 指定方案的满足度分析
```

报告结构：

```json
{
  "report_version": "v3_teacher_profile_satisfaction_mvp",
  "scheme_count": 1,
  "schemes": [
    {
      "scheme_index": 1,
      "summary": {...},
      "low_satisfaction_teachers": [...],
      "teacher_reports": [...]
    }
  ]
}
```

---

## 代码位置

| 文件 | 职责 |
|------|------|
| `ml/scheduling_v3/teacher_profiles.py` | V3 教师画像提取 + 满足度分析 CLI |

核心函数：

| 函数 | 职责 |
|------|------|
| `derive_profiles_from_real_dataset()` | 从清洗后的真实课表生成教师画像 |
| `analyze_scheme_satisfaction()` | 分析 `schemes.jsonl` 的教师画像满足度 |

---

## 与向量库的关系

本 MVP 不使用向量库。

后续如接入，向量库的定位是：

```text
教师备注 / 调课说明 / 审批意见
  → embedding
  → 教师画像证据库
  → 用于解释、相似案例检索、辅助 LLM 分类
```

向量库不是画像本体。画像本体仍是可计算的结构化字段。

---

## 后续阶段

### Phase 2：声明画像与反馈画像合并

- 接入 Java `teacher_profile` 表中的教师声明画像
- 接入调课申请说明，LLM 分类为结构化反馈信号
- 形成来源优先级：教师编辑 > LLM 声明 > 调课反馈 > 历史数据

### Phase 3：进入 CP-SAT 软目标

- 在 task plan 中计算 `teacher_profile_satisfaction_score`
- CP-SAT objective 加入教师画像满足度权重
- 输出方案时带上画像解释

### Phase 4：进入 Placement Model 特征

- 将画像字段加入训练样本特征
- 重训 Placement Model
- 对比 hit@k 与课表满足度变化
