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
	│   ├── 03-LightGBM模型训练架构设计.md
	│   ├── 04-训练样本事件采集架构设计.md
	│   ├── 05-模型训练数据链路设计.md
	│   ├── 06-真实课表导入字段模板.md
	│   ├── 07-AI生成课表人工筛选标准.md
	│   ├── 08-模型消融实验设计方案.md
	│   ├── 09-GA编码与适应度函数设计.md
	│   ├── 10-LightGBM选型与模型对比说明.md
	│   └── 11-核心链路论文版总设计.md
├── implementation/
│   ├── 01-GA排课生成链路实现说明.md
│   ├── 02-教师画像JSONL快照接入说明.md
│   └── 03-排课链路验证与排障说明.md
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
| architecture/01-排课架构设计.md | 完整链路、数据模型、编码规则、预处理、GA 各环节 |
| architecture/02-教师画像作用路径设计.md | 教师自然语言画像、LLM 结构化、JSONL 快照、Python 排课消费路径 |
| architecture/03-LightGBM模型训练架构设计.md | 规则冷启动、反馈样本、模型训练、评估发布、GA 推理加载 |
| architecture/04-训练样本事件采集架构设计.md | 事件表、行为快照、调整相消、人工标注和样本构建边界 |
| architecture/05-模型训练数据链路设计.md | 真实课表/AI满意课表采集、片段级样本、标签权重、sigmoid归一化和消融实验数据基础 |
| architecture/06-真实课表导入字段模板.md | 学校真实课表导入字段、周次/节次标准化、名称映射、质量检查和片段样本转换 |
| architecture/07-AI生成课表人工筛选标准.md | AI生成候选课表的方案级/片段级人工筛选、标签权重、不满意原因和样本转换规则 |
| architecture/08-模型消融实验设计方案.md | 规则、RandomForest、LightGBM、教师画像增强等评分器的消融实验分组、指标和分析口径 |
| architecture/09-GA编码与适应度函数设计.md | GA染色体/基因编码、硬软约束、适应度函数、sigmoid评分接入、遗传操作和答辩口径 |
| architecture/10-LightGBM选型与模型对比说明.md | LightGBM选型理由、与RandomForest/XGBoost/纯规则/深度学习对比、消融实验和答辩口径 |
| architecture/11-核心链路论文版总设计.md | 项目论文版总纲，串联教师画像、训练样本、LightGBM评分、GA优化、反馈闭环和消融实验 |
| implementation/01-GA排课生成链路实现说明.md | Java→Python→SSE→schemes.json→入库的具体代码路径 |
| implementation/02-教师画像JSONL快照接入说明.md | 教师画像快照导出、请求传递、Python 归一化和排课消费实现 |
| implementation/03-排课链路验证与排障说明.md | 本地验证命令、关键输出文件、常见问题定位 |
| thesis/01-论文目录与章节要点.md | 毕业论文题目、章节结构、每章要点、对应项目文档和待补实验材料 |
| thesis/02-答辩PPT大纲.md | 答辩PPT故事线、页面结构、每页讲述重点和后续素材清单 |
| thesis/03-核心图清单与草图说明.md | 论文和PPT核心图规划、草图说明、放置位置和后续绘制优先级 |
| thesis/04-核心图Mermaid草稿.md | 总体路线、训练链路、LightGBM+GA、GA编码、教师画像和消融实验的 Mermaid 图稿 |
| thesis/05-论文与答辩材料待办清单.md | 当前已完成材料、数据/实验/素材缺口、P0-P2优先级和最小可交付版本 |
| feedback/01-排课真实数据验收反馈.md | 真实任务验收中的非阻塞问题、判断和后续优化项 |
| roadmap/01-训练样本收集优先路线.md | 训练样本事件采集、样本构建和重训准备的后续建设顺序 |

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
