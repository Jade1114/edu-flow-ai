# Edu-Flow-AI 文档索引

> 更新时间：2026-05-21
> 原则：项目文档统一维护在本仓库 `docs/` 下；药柜中的旧笔记仅作为历史来源，不再作为项目当前文档入口。

## 文档结构

```text
docs/
├── README.md
├── architecture/
│   ├── 01-排课架构设计.md
│   ├── 02-模型反馈训练闭环.md
│   ├── 03-排课方案生成总链路.md
│   └── 04-排课链路待实现清单.md
├── ml/
│   └── 01-LightGBM训练样本与实施记录.md
└── roadmap/
    └── 01-排课执行表.md
```

## 文件职责

| 文档 | 职责 | 更新时机 |
|---|---|---|
| `architecture/01-排课架构设计.md` | 稳定架构、组件分工、数据流边界 | 架构边界变化时 |
| `architecture/02-模型反馈训练闭环.md` | 反馈数据、训练接口、重训链路 | 反馈训练能力变化时 |
| `architecture/03-排课方案生成总链路.md` | 从排课任务到候选方案展示的端到端链路 | 链路节点变化时 |
| `architecture/04-排课链路待实现清单.md` | 当前真实 TODO 和已完成项 | 每轮实现后 |
| `ml/01-LightGBM训练样本与实施记录.md` | 训练样本字段、训练脚本、模型产物、实施记录 | 训练流程变化时 |
| `roadmap/01-排课执行表.md` | 项目阶段、能力边界、下一步计划 | 阶段推进后 |

## 当前架构边界

```text
LLM Parser：自然语言规则解析 + 教师画像结构化 + 权重建议，不直接生成课表
Constraint Engine：硬约束裁剪 DNA，生成可行候选空间
遗传算法：完整课表方案层面的全局组合优化，构造后 repair / validate
LightGBM Ranker：只对合法候选或 Top-K 合法课表做满意度 / 偏好重排
Java 后端：任务编排、生成配置入库、教师画像解析、提交 ML API 任务、轮询结果、结果入库、确认发布
前端：编辑任务生成配置、策略预设展开、方案展示、画像扣分解释、调整、确认、模型训练中心反馈入口
```

正式生成链路已收敛为 LLM Parser + Constraint Engine + GA + LightGBM Ranker；Java 只向 ML API 提交 `allocation_task_id`，Python 从数据库读取任务配置和教师画像偏好。历史实验入口不再作为当前文档事实源。

## 药柜迁移说明

已从 `~/Apothecary-Vault/projects/edu-flow-ai/features/` 迁移仍有价值的内容：

- `00-INDEX.md` → 合并为本文件
- `01-排课架构设计.md` → 合并进 `architecture/01-排课架构设计.md`
- `02-训练样本字段表.md` → 迁移为 `ml/01-LightGBM训练样本与实施记录.md`
- `03-排课执行表.md` → 迁移为 `roadmap/01-排课执行表.md`

药柜 `archive/` 中的 MVP 早期设计、旧分课/调课笔记已被当前实现覆盖，不再迁移为当前文档。
