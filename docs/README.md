# Edu-Flow-AI 文档索引

> 更新时间：2026-05-31
> 原则：项目文档统一维护在本仓库 `docs/` 下。

## 文档结构

```text
docs/
├── README.md
├── architecture/            ← 架构设计
│   ├── 15-基于候选空间压缩与学习评分引导的智能排课架构.md  ← 最终排课架构 ★
│   ├── 02-教师画像作用路径设计.md
│   ├── 03-LightGBM模型训练架构设计.md
│   ├── 04-训练样本事件采集架构设计.md
│   ├── 05-模型训练数据链路设计.md
│   ├── 06-真实课表导入字段模板.md
│   ├── 07-AI生成课表人工筛选标准.md
│   ├── 08-模型消融实验设计方案.md
│   ├── 10-LightGBM选型与模型对比说明.md
│   ├── 12-数据闭环与画像演进设计.md
│   └── 13-评分体系与约束分层设计.md
├── implementation/          ← 实现说明
│   ├── 02-教师画像JSONL快照接入说明.md
│   ├── 03-排课链路验证与排障说明.md
│   ├── 04-scoring-config-fields-migration.sql
│   └── 05-真实课表数据导入流程.md
├── archive/                 ← 历史存档（旧 GA / Beam Search 方案，已过时）
│   ├── README.md
│   ├── 01-排课架构设计.md
│   ├── 09-GA编码与适应度函数设计.md
│   ├── 11-核心链路论文版总设计.md
│   ├── 14-双通道排课架构设计.md
│   └── 01-GA排课生成链路实现说明.md
├── thesis/
│   ├── 01-论文目录与章节要点.md
│   ├── 02-答辩PPT大纲.md
│   ├── 03-核心图清单与草图说明.md
│   ├── 04-核心图Mermaid草稿.md
│   └── 05-论文与答辩材料待办清单.md
├── feedback/
│   └── 01-排课真实数据验收反馈.md
└── roadmap/
    └── 01-训练样本收集优先路线.md
```

## 文件职责

| 文档 | 职责 |
|------|------|
| **architecture/15-基于候选空间压缩...md** | ★ 最终排课架构：学习引导候选集生成 + GA 全局组合优化 |
| architecture/02-教师画像作用路径设计.md | 教师自然语言画像、LLM 结构化、JSONL 快照、Python 排课消费路径 |
| architecture/03-LightGBM模型训练架构设计.md | 规则冷启动、反馈样本、模型训练、评估发布 |
| architecture/04-训练样本事件采集架构设计.md | 事件表、行为快照、调整相消、人工标注和样本构建边界 |
| architecture/05-模型训练数据链路设计.md | 真实课表/AI满意课表采集、片段级样本、标签权重、sigmoid归一化 |
| architecture/06-真实课表导入字段模板.md | 学校真实课表导入字段、周次/节次标准化、名称映射、质量检查 |
| architecture/07-AI生成课表人工筛选标准.md | AI生成候选课表的方案级/片段级人工筛选、标签权重、不满意原因 |
| architecture/08-模型消融实验设计方案.md | 评分器消融实验分组、指标和分析口径 |
| architecture/10-LightGBM选型与模型对比说明.md | LightGBM选型理由、与RF/XGBoost/深度学习对比、答辩口径 |
| architecture/12-数据闭环与画像演进设计.md | 数据获取、特征工程、数据漂移、画像动态演进 |
| architecture/13-评分体系与约束分层设计.md | 5层评分架构、penalty/quality分流、config参数设计 |
| implementation/02-教师画像JSONL快照接入说明.md | 教师画像快照导出、请求传递、Python 归一化 |
| implementation/03-排课链路验证与排障说明.md | 本地验证命令、关键输出文件、常见问题定位 |
| implementation/05-真实课表数据导入流程.md | 全校课表 XLS → JSONL → MySQL 完整数据管道 |
| thesis/01-论文目录与章节要点.md | 毕业论文题目、章节结构、每章要点、对应项目文档和待补实验材料 |
| thesis/02-答辩PPT大纲.md | 答辩PPT故事线、页面结构、每页讲述重点和后续素材清单 |
| thesis/03-核心图清单与草图说明.md | 论文和PPT核心图规划、草图说明、放置位置和后续绘制优先级 |
| thesis/04-核心图Mermaid草稿.md | 总体路线、训练链路、LightGBM+GA、GA编码、教师画像和消融实验的 Mermaid 图稿 |
| thesis/05-论文与答辩材料待办清单.md | 当前已完成材料、数据/实验/素材缺口、P0-P2优先级和最小可交付版本 |
| feedback/01-排课真实数据验收反馈.md | 真实任务验收中的非阻塞问题、判断和后续优化项 |
| roadmap/01-训练样本收集优先路线.md | 训练样本事件采集、样本构建和重训准备的后续建设顺序 |

## 当前架构边界

```text
核心思路：模型生成高质量候选集，GA 组合全校无冲突课表
输入接口：Java 仅传 allocation_task_id
候选生成：Template Generator + Room Ranker + Placement Scorer
候选粒度：每个 teaching_task 的完整排课候选，不是单个 slot
GA 编码：gene = candidate_index，chromosome = 全校 teaching_task 候选索引
Fitness：硬约束 O(n) 检测 + 教师画像 + 影响因子 + Scorer 预评分
```

正式链路：`allocation_task_id` → Python 加载数据 → 候选池构建 → GA 初始化 →
GA 搜索 → fitness 评估 → TopK 方案 → Java 入库 → 人工调课反馈。

实现细节优先看 `docs/architecture/15-*`，`docs/archive/` 为历史参考。
