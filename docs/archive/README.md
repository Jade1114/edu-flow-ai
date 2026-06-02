# 历史架构文档存档

> 以下文档已被 [最终排课架构](../architecture/15-基于候选空间压缩与学习评分引导的智能排课架构.md) 取代。
> 仅供历史参考，不再作为当前实现依据。

## 当前架构变化

旧 GA 主线直接在 `slot × classroom` 空间内搜索，搜索空间过大。
V2 Beam Search 将 LightGBM 植入构造过程，但弱化了 GA 的全局组合能力。

当前最终架构采用：

```text
学习模型生成并预评分 teaching_task 级完整候选
  ↓
GA 在 candidate_index 空间做全校组合优化
  ↓
fitness 用硬约束、教师画像和影响因子统一评估
```

详见主架构文档。
