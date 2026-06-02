# Edu-Flow-AI 文档索引

> 更新时间：2026-06-02  
> 原则：项目文档统一维护在本仓库 `docs/` 下。

---

## 文档结构

```text
docs/
├── README.md                                    ← 本文件
├── architecture/                                ← 架构设计
│   ├── 17-V3-CP-SAT排课架构设计.md               ← ★ 当前排课架构 (V3)
│   ├── 03-LightGBM模型训练架构设计.md
│   ├── 04-训练样本事件采集架构设计.md
│   ├── 05-模型训练数据链路设计.md
│   ├── 06-真实课表导入字段模板.md
│   ├── 07-AI生成课表人工筛选标准.md
│   ├── 08-模型消融实验设计方案.md
│   ├── 10-LightGBM选型与模型对比说明.md
│   ├── 12-数据闭环与画像演进设计.md
│   └── 02-教师画像作用路径设计.md
├── implementation/                              ← 实现说明
│   ├── 02-教师画像JSONL快照接入说明.md
│   ├── 03-排课链路验证与排障说明.md
│   ├── 04-scoring-config-fields-migration.sql
│   └── 05-真实课表数据导入流程.md
├── archive/                                     ← 历史存档
│   ├── README.md
│   ├── 01-排课架构设计.md                        (V1 GA)
│   ├── 09-GA编码与适应度函数设计.md
│   ├── 11-核心链路论文版总设计.md
│   ├── 14-双通道排课架构设计.md                   (V2 启发 V3)
│   ├── 15-基于候选空间压缩...md                   (V2.5 候选池 GA)
│   ├── 16-实时排课简化方案.md                     (V2 Beam Search)
│   ├── 01-GA排课生成链路实现说明.md
│   └── 13-评分体系与约束分层设计.md               (V2 GA scoring)
├── thesis/
│   ├── 01-论文目录与章节要点.md
│   ├── 02-答辩PPT大纲.md
│   ├── 03-核心图清单与草图说明.md
│   ├── 04-核心图Mermaid草稿.md
│   ├── 05-论文与答辩材料待办清单.md
│   └── 06-GA编码设计技术选型依据.md
├── feedback/
│   └── 01-排课真实数据验收反馈.md
└── roadmap/
    ├── 01-训练样本收集优先路线.md
    └── 02-理论与实验设计推进路线.md
```

---

## 文件职责

| 文档 | 职责 | 状态 |
|------|------|------|
| **architecture/17-V3-CP-SAT排课架构设计.md** | ★ 当前架构：Placement Model + CP-SAT 全局方案选择 | ✅ 生产 |
| architecture/03-LightGBM模型训练架构设计.md | 训练闭环设计（规则冷启动→反馈重训），V3 placement model 的训练方法论 | ⚠️ 需更新 |
| architecture/04-训练样本事件采集架构设计.md | 事件表、行为快照、调整相消、人工标注 | ⚠️ 需更新 |
| architecture/05-模型训练数据链路设计.md | 真实课表→片段级样本→标签权重→sigmoid归一化 | ⚠️ 需更新 |
| architecture/06-真实课表导入字段模板.md | 学校真实课表导入字段、标准化 | ✅ 仍适用 |
| architecture/07-AI生成课表人工筛选标准.md | 方案级/片段级人工筛选标准 | ✅ 仍适用 |
| architecture/08-模型消融实验设计方案.md | 评分器消融实验分组 | ⚠️ 需适配 V3 |
| architecture/10-LightGBM选型与模型对比说明.md | LightGBM vs RF/XGBoost/深度学习 | ✅ 仍适用 |
| architecture/12-数据闭环与画像演进设计.md | 数据获取、特征工程、数据漂移、画像演进 | ⚠️ 需更新 |
| architecture/02-教师画像作用路径设计.md | 教师画像在排课中的作用路径 | ⚠️ V3 尚未接入 |
| implementation/02-教师画像JSONL快照接入说明.md | 画像快照导出与传递 | ⚠️ 待 V3 适配 |
| implementation/03-排课链路验证与排障说明.md | 本地验证命令、常见问题 | 🔴 已过时 (V2) |
| implementation/05-真实课表数据导入流程.md | XLS→JSONL→MySQL 管道 | ✅ 仍适用 |
| thesis/* | 论文与答辩材料 | ⚠️ 需更新为 V3 |
| feedback/01-排课真实数据验收反馈.md | V2 验收中的非阻塞问题 | ⚠️ 部分已修复 |
| roadmap/01-训练样本收集优先路线.md | 样本收集路线 | ⚠️ 需更新 |
| roadmap/02-理论与实验设计推进路线.md | 理论实验推进 | ⚠️ 需更新 |

---

## 当前架构边界

```text
核心思路: Placement Model 生成候选 → CP-SAT 全局无冲突选择

输入接口: Java 仅传 allocation_task_id
候选粒度: 每个 teaching_task 的完整 task plan (教室 + day/period + 周次分布)
求解方式: OR-Tools CP-SAT 约束求解 (硬约束建模, 软目标优化)
多方案:   scheme_count 个独立求解 (互不重复)
输出:     schemes.jsonl → Java 入库 → 冲突检测 → 前端展示

模型:     LightGBM 多分类 (3953 类, 13 特征)
训练数据: 从真实课表提取 (11,443 样本)
数据规模: 2615 teaching tasks, 330 classrooms, 673 courses, 624 teachers
```

正式链路：`allocation_task_id` → Python 加载 DB 数据 → Placement Model TopK 推理 →
Task Plans 模板生成 → CP-SAT 全局方案选择 → `schemes.jsonl` 输出 →
Java 入库 → 冲突检测 → 前端 SSE 展示。

实现细节优先看 `docs/architecture/17-V3-*`，`docs/archive/` 为 V1/V2 历史参考。
