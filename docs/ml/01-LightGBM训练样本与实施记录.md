# LightGBM 训练样本与实施记录

> 更新时间：2026-05-18  
> 来源：由药柜 `projects/edu-flow-ai/features/02-训练样本字段表.md` 迁移并按当前代码状态更新。

## 模型定位

第一版排课模型不是自然语言生成器，而是候选排课决策评分器：

```text
教学任务 + 候选时间片 + 候选教室 + 当前课表状态 → 合理性分数 score
```

Java/Python 生成候选组合，LightGBM 对候选片段评分；下一阶段由遗传算法在完整方案层面搜索全局更优组合。正式课表只在教务确认方案后写入 `course_assignment`。

## 样本含义

一行训练样本代表一个候选排课动作：某个教学任务被安排到某个时间片、某个教室，在当前课表状态下是否合理。

## 第一版字段集

```text
course_type, total_hours, required_room_type, class_group_count, total_student_count,
teacher_department, teacher_title, teacher_max_weekly_hours,
room_capacity, room_type, room_building, capacity_margin, capacity_ratio,
week_number, day_of_week, period_index, is_morning, is_afternoon, is_evening,
is_early_period, is_late_period,
teacher_occupied_at_slot, class_occupied_at_slot, room_occupied_at_slot,
teacher_day_load, class_day_load, teacher_week_load, class_week_load,
is_capacity_enough, is_room_type_match,
has_teacher_conflict, has_class_conflict, has_room_conflict, has_hard_conflict,
score
```

字段分为：教学任务特征、课程特征、教师特征、教学班特征、教室特征、时间片特征、当前课表状态特征、规则/偏好特征、标签字段。

## 标签生成规则

规则构造样本阶段的基础标签：

```text
if has_hard_conflict = 1: score = 0
else:
  score = 0.60
  if is_room_type_match = 1:         +0.10
  if 0.50 <= capacity_ratio <= 0.90: +0.10
  if not early and not late:         +0.05
  if teacher_day_load <= 3:          +0.05
  if class_day_load <= 3:            +0.05
  if week_load within limits:        +0.05
  clip to [0, 1]
```

反馈训练阶段会从确认方案、拒绝方案、冲突明细、人工调整前后构造正负样本，并附加 `sample_weight`。

## ML 目录

```text
server/ml/
├── README.md
├── requirements.txt
├── prompts/
│   ├── teacher-penalty-system.md
│   └── teacher-penalty-user-template.md
├── data/              # 生成数据，按 .gitignore 排除
├── models/            # 模型产物，按 .gitignore 排除
└── scripts/
    ├── generate_training_samples.py
    ├── train_lightgbm.py
    ├── predict_demo.py
    ├── evaluate_model.py
    ├── generate_scheme_ga.py        # 主生成入口
    ├── evaluate_scheme_demo.py
    └── build_feedback_training_samples.py
```

## 核心脚本

| 脚本 | 职责 | 当前状态 |
|---|---|:--:|
| `generate_training_samples.py` | 从数据库生成规则构造训练样本 | ✅ |
| `train_lightgbm.py` | 训练 LightGBM 排课评分模型 | ✅ |
| `predict_demo.py` | 加载模型并预测候选片段分数 | ✅ |
| `evaluate_model.py` | 评估模型指标和特征重要性 | ✅ |
| `generate_scheme_ga.py` | 遗传算法全局搜索完整方案，主生成入口 | ✅ |
| `evaluate_scheme_demo.py` | 评估方案级质量和教师画像满意度 | ✅ |
| `build_feedback_training_samples.py` | 将反馈 JSON 转为训练 CSV | ✅ |

## 第一阶段训练结果

基于规则构造样本完成第一版训练：

```text
样本数：113400
特征数：34
类别特征数：6
模型文件：server/ml/models/base/schedule_ranker_v1.txt
特征 schema：server/ml/models/base/feature_schema.json
```

评估结果接近满分，是因为第一版标签由规则自动生成，模型主要学习规则评分逻辑；这不代表已经学习到真实教务偏好。真实偏好需要通过反馈训练闭环逐步积累。

## 方案生成链路

```text
教学任务片段列表
↓
Constraint Engine 裁剪硬非法 DNA
↓
每个片段构造硬合法候选池
↓
遗传算法组合完整方案，并执行 repair / validate
↓
Top-K 硬合法候选课表
↓
LightGBM 对合法候选或完整方案做偏好重排
↓
输出 scheme_001~N.csv + teacher_penalties.json + ga_summary.json
```

## 教师画像惩罚

当前实现直接读取 MySQL 中已结构化的教师画像偏好，不再走 Embedding / Qdrant 检索：

```text
教学任务上下文
↓
读取 teacher_profile.profile_preference_json
↓
teacher_penalties.json
↓
生成器评分阶段扣分 + 评估器满意度计算
```

相关 prompt 当前归 Java 资源目录管理：

- `server/src/main/resources/prompts/teacher-penalty-system.md`
- `server/src/main/resources/prompts/teacher-penalty-user-template.md`

Python 侧旧画像 RAG prompt 已删除；教师画像“其他说明”的 LLM 解析只保留 Java resources 中的一份 prompt。

需要的环境变量包括：`OPENAI_CHAT_API_KEY`、`OPENAI_CHAT_BASE_URL`、`OPENAI_CHAT_MODEL`。

## 与业务表对应

| 能力 | 表/对象 |
|---|---|
| 教学任务 | `teaching_task` / `TeachingTask` |
| 课程 | `course` / `Course` |
| 教师 | `teacher` / `Teacher` |
| 教师画像 | `teacher_profile` |
| 教学班 | `class_group` / `ClassGroup` |
| 教室 | `classroom` / `Classroom` |
| 时间片 | `time_slot` / `TimeSlot` |
| 候选方案 | `allocation_scheme` |
| 候选片段 | `allocation_item` |
| 正式课表 | `course_assignment` |
| 冲突结果 | `conflict_check_result` |
| 反馈数据 | `allocation_scheme_feedback`、`allocation_item_adjustment_log` |

## 常用命令

```bash
cd server/ml
source .venv/bin/activate
python scripts/generate_training_samples.py
python scripts/train_lightgbm.py
python scripts/generate_scheme_ga.py --variant-count 5 --policy BALANCED --exclude-weekends --population-size 80 --generations 80 --teacher-penalties data/generated/teacher_penalties.json
python scripts/evaluate_scheme_demo.py --scheme-dir data/generated --json --teacher-penalties data/generated/teacher_penalties.json
```

后端触发反馈训练见 `docs/architecture/02-模型反馈训练闭环.md`。
