# Edu-Flow-AI 文档索引

> 更新时间：2026-05-25
> 原则：项目文档统一维护在本仓库 `docs/` 下。

## 文档结构

```text
docs/
├── README.md
├── architecture/
│   ├── 01-排课架构设计.md
│   ├── 02-教师画像作用路径设计.md
│   └── 03-LightGBM模型训练架构设计.md
├── implementation/
│   ├── 01-GA排课生成链路实现说明.md
│   ├── 02-教师画像JSONL快照接入说明.md
│   └── 03-排课链路验证与排障说明.md
└── feedback/
    └── 01-排课真实数据验收反馈.md
```

## 文件职责

| 文档 | 职责 |
|------|------|
| architecture/01-排课架构设计.md | 完整链路、数据模型、编码规则、预处理、GA 各环节 |
| architecture/02-教师画像作用路径设计.md | 教师自然语言画像、LLM 结构化、JSONL 快照、Python 排课消费路径 |
| architecture/03-LightGBM模型训练架构设计.md | 规则冷启动、反馈样本、模型训练、评估发布、GA 推理加载 |
| implementation/01-GA排课生成链路实现说明.md | Java→Python→SSE→schemes.json→入库的具体代码路径 |
| implementation/02-教师画像JSONL快照接入说明.md | 教师画像快照导出、请求传递、Python 归一化和排课消费实现 |
| implementation/03-排课链路验证与排障说明.md | 本地验证命令、关键输出文件、常见问题定位 |
| feedback/01-排课真实数据验收反馈.md | 真实任务验收中的非阻塞问题、判断和后续优化项 |

## 当前架构边界

```text
模板集枚举器：按总课次拆分周负载，bitmask 周编码，三段评分
GA 染色体：[TaskGene(templateSetId, [slotId, classroomId]), ...]
GA 初始：MRV 贪心（最长→最重→最大）
GA 交叉：task-level uniform（不拆模板）
GA 修复：主优化器，delta min 候选选择
适应度：硬冲突1M + 模板惩罚 + 同天重复 + 晚课
```

正式生成链路已收敛为「模板枚举 → AllocationTask → GA 进化 → schemes.json → Java 入库」。历史实验链路已全部清理。

实现细节优先看 `docs/implementation/`，架构文档只描述边界和设计原则。
