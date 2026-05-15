<script setup>
import { computed, ref } from 'vue'
import {
  ChatDotRound,
  Cpu,
  DataAnalysis,
  Finished,
  MagicStick,
  TrendCharts,
  Warning,
} from '@element-plus/icons-vue'

const activeWeek = ref(1)

const llmMetrics = [
  { label: '生成方式', value: '文本推理 + JSON 解析', tone: 'warning' },
  { label: '硬约束稳定性', value: '依赖提示词约束', tone: 'danger' },
  { label: '方案一致性', value: '波动较大', tone: 'warning' },
  { label: '可解释性', value: '语言解释强', tone: 'success' },
  { label: '速度', value: '等待模型响应', tone: 'warning' },
]

const mlMetrics = [
  { label: '生成方式', value: '候选评分 + 状态选择', tone: 'success' },
  { label: '硬约束稳定性', value: '规则强制兜底', tone: 'success' },
  { label: '方案一致性', value: '稳定可复现', tone: 'success' },
  { label: '可解释性', value: '指标解释清晰', tone: 'success' },
  { label: '速度', value: '本地批量生成', tone: 'success' },
]

const comparisonRows = [
  {
    dimension: '决策方式',
    llm: '一次性生成整段排课文本，系统再尝试解析',
    ml: '逐个片段生成候选，由模型对时间片和教室组合评分',
  },
  {
    dimension: '硬约束处理',
    llm: '通过 Prompt 告诉模型不要冲突，但不能天然保证',
    ml: '教师、班级、教室、容量、类型由规则系统实时校验',
  },
  {
    dimension: '软约束处理',
    llm: '能理解偏好，但输出不稳定，难以量化调参',
    ml: '通过权重、特征、方案评分持续优化分布和偏好',
  },
  {
    dimension: '多方案能力',
    llm: '多次请求得到多份文本，质量差异难比较',
    ml: '批量生成多个方案，并用方案级指标统一排名',
  },
  {
    dimension: '落地形态',
    llm: '适合解释、总结、辅助教务理解方案',
    ml: '适合承担核心排课决策，输出可检测、可保存方案',
  },
]

const llmWeekdayLoad = [124, 103, 67, 36, 23, 15, 10]
const mlWeekdayLoad = [54, 54, 54, 54, 54, 54, 54]
const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const llmPeriodLoad = [0, 135, 133, 110, 0]
const mlPeriodLoad = [0, 63, 163, 152, 0]
const periods = ['第1节', '第2节', '第3节', '第4节', '第5节']

const schemeCards = [
  {
    name: 'LLM 旧链路示意',
    score: 78,
    conflict: '需二次检测',
    balance: '星期分布偏前',
    summary: '适合解释排课思路，但不适合作为硬约束排课核心。',
    type: 'warning',
  },
  {
    name: '自训练模型方案 001',
    score: 99.9983,
    conflict: '0 硬冲突',
    balance: '53~55/天',
    summary: '模型评分负责选择，规则系统兜底，方案级评估器排名。',
    type: 'success',
  },
  {
    name: '自训练模型方案 002',
    score: 99.9982,
    conflict: '0 硬冲突',
    balance: '53~55/天',
    summary: '支持多方案生成，可在管理端进一步人工确认和微调。',
    type: 'success',
  },
]

const flowSteps = [
  {
    title: 'LLM 旧链路',
    icon: ChatDotRound,
    steps: ['拼接 Prompt', 'LLM 生成文本', '解析 JSON', '保存方案', '冲突检测补救'],
  },
  {
    title: '自训练模型链路',
    icon: Cpu,
    steps: ['构造候选', 'LightGBM 评分', '规则预筛', '状态惩罚修正', '多方案评分排名'],
  },
]

const maxWeekdayLoad = computed(() => Math.max(...llmWeekdayLoad, ...mlWeekdayLoad))
const maxPeriodLoad = computed(() => Math.max(...llmPeriodLoad, ...mlPeriodLoad))

function barWidth(value, maxValue) {
  if (!maxValue) return '0%'
  return `${Math.max(4, Math.round((value / maxValue) * 100))}%`
}
</script>

<template>
  <div class="compare-page">
    <div class="hero-card">
      <div>
        <p class="eyebrow">AI 排课能力对比</p>
        <h2>LLM 生成方案 vs 自训练模型生成方案</h2>
        <p class="hero-text">
          这个页面用于直观看到两种路线的差异：LLM 更适合解释和辅助，
          自训练模型更适合承担核心排课决策，并通过规则和评分保证方案质量。
        </p>
      </div>
      <div class="hero-actions">
        <el-tag type="success" size="large">自训练模型：0 硬冲突</el-tag>
        <el-tag type="warning" size="large">LLM：偏辅助解释</el-tag>
      </div>
    </div>

    <el-row :gutter="16" class="section-row">
      <el-col :span="12">
        <el-card shadow="never" class="method-card llm-card">
          <template #header>
            <div class="card-header">
              <el-icon><ChatDotRound /></el-icon>
              <span>LLM 方案生成</span>
            </div>
          </template>
          <p class="method-desc">
            LLM 可以理解自然语言要求，也能解释为什么这样排，但它本质上是生成文本，
            对教师、班级、教室冲突这类硬约束没有天然保证。
          </p>
          <div class="metric-grid">
            <div v-for="metric in llmMetrics" :key="metric.label" class="metric-item">
              <span>{{ metric.label }}</span>
              <el-tag :type="metric.tone" size="small">{{ metric.value }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="method-card ml-card">
          <template #header>
            <div class="card-header">
              <el-icon><Cpu /></el-icon>
              <span>自训练模型方案生成</span>
            </div>
          </template>
          <p class="method-desc">
            LightGBM 不直接写文本，而是对“教学任务 × 时间片 × 教室”的候选组合评分，
            再由规则系统和在线选择器把连续选择组织成完整课表。
          </p>
          <div class="metric-grid">
            <div v-for="metric in mlMetrics" :key="metric.label" class="metric-item">
              <span>{{ metric.label }}</span>
              <el-tag :type="metric.tone" size="small">{{ metric.value }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-row">
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><MagicStick /></el-icon>
              <span>生成链路差异</span>
            </div>
          </template>
          <div class="flow-board">
            <div v-for="flow in flowSteps" :key="flow.title" class="flow-column">
              <div class="flow-title">
                <el-icon><component :is="flow.icon" /></el-icon>
                {{ flow.title }}
              </div>
              <div v-for="(step, index) in flow.steps" :key="step" class="flow-step">
                <span>{{ index + 1 }}</span>
                {{ step }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><DataAnalysis /></el-icon>
              <span>关键能力对照</span>
            </div>
          </template>
          <el-table :data="comparisonRows" size="small" border>
            <el-table-column prop="dimension" label="维度" width="110" />
            <el-table-column prop="llm" label="LLM" />
            <el-table-column prop="ml" label="自训练模型" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-row">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><TrendCharts /></el-icon>
              <span>星期分布对比</span>
            </div>
          </template>
          <div class="chart-block">
            <div v-for="(day, index) in days" :key="day" class="bar-row">
              <span class="bar-label">{{ day }}</span>
              <div class="bar-track">
                <div class="bar llm-bar" :style="{ width: barWidth(llmWeekdayLoad[index], maxWeekdayLoad) }">
                  {{ llmWeekdayLoad[index] }}
                </div>
              </div>
              <div class="bar-track">
                <div class="bar ml-bar" :style="{ width: barWidth(mlWeekdayLoad[index], maxWeekdayLoad) }">
                  {{ mlWeekdayLoad[index] }}
                </div>
              </div>
            </div>
          </div>
          <div class="legend">
            <span><i class="legend-dot llm-dot" />LLM 旧链路示意</span>
            <span><i class="legend-dot ml-dot" />自训练模型实测</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><Finished /></el-icon>
              <span>方案排名结果</span>
            </div>
          </template>
          <div class="scheme-list">
            <div v-for="scheme in schemeCards" :key="scheme.name" class="scheme-card">
              <div class="scheme-head">
                <strong>{{ scheme.name }}</strong>
                <el-tag :type="scheme.type" size="small">{{ scheme.score }}</el-tag>
              </div>
              <div class="scheme-meta">
                <span>{{ scheme.conflict }}</span>
                <span>{{ scheme.balance }}</span>
              </div>
              <p>{{ scheme.summary }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-row">
      <template #header>
        <div class="card-header">
          <el-icon><Warning /></el-icon>
          <span>展示结论</span>
        </div>
      </template>
      <el-alert
        type="success"
        show-icon
        :closable="false"
        title="当前结论：LLM 适合做解释层，自训练模型适合做决策层。"
        description="后续接入 Java 后，可以把这里的静态对比替换为真实任务的 LLM 方案、自训练模型方案、冲突检测结果和人工确认反馈。"
      />
    </el-card>
  </div>
</template>

<style scoped>
.compare-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  border-radius: 14px;
  background: linear-gradient(135deg, #eef5ff 0%, #f7fbff 48%, #f8fff7 100%);
  border: 1px solid var(--el-border-color-light);
}
.eyebrow {
  margin: 0 0 6px;
  color: #409eff;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.hero-card h2 {
  margin: 0 0 10px;
  font-size: 26px;
}
.hero-text {
  max-width: 760px;
  margin: 0;
  color: #606266;
  line-height: 1.7;
}
.hero-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 10px;
  min-width: 180px;
}
.section-row {
  margin-top: 0;
}
.method-card {
  height: 100%;
  border-top: 4px solid transparent;
}
.llm-card {
  border-top-color: #e6a23c;
}
.ml-card {
  border-top-color: #67c23a;
}
.card-header,
.flow-title,
.scheme-head,
.legend {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-header {
  font-weight: 700;
}
.method-desc {
  min-height: 66px;
  margin: 0 0 16px;
  color: #606266;
  line-height: 1.7;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
}
.metric-item span {
  color: #606266;
  font-size: 13px;
}
.flow-board {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.flow-column {
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
}
.flow-title {
  margin-bottom: 10px;
  font-weight: 700;
}
.flow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
}
.flow-step span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  font-weight: 700;
}
.chart-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bar-row {
  display: grid;
  grid-template-columns: 48px 1fr 1fr;
  align-items: center;
  gap: 10px;
}
.bar-label {
  color: #606266;
  font-size: 13px;
}
.bar-track {
  height: 24px;
  border-radius: 999px;
  background: #f1f5f9;
  overflow: hidden;
}
.bar {
  height: 100%;
  padding-right: 8px;
  border-radius: 999px;
  color: #fff;
  font-size: 12px;
  line-height: 24px;
  text-align: right;
  transition: width 0.2s ease;
}
.llm-bar {
  background: linear-gradient(90deg, #f3c78a, #e6a23c);
}
.ml-bar {
  background: linear-gradient(90deg, #95d475, #67c23a);
}
.legend {
  margin-top: 14px;
  color: #909399;
  font-size: 12px;
}
.legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 5px;
  border-radius: 50%;
}
.llm-dot {
  background: #e6a23c;
}
.ml-dot {
  background: #67c23a;
}
.scheme-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.scheme-card {
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: #fff;
}
.scheme-head {
  justify-content: space-between;
  margin-bottom: 8px;
}
.scheme-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  color: #606266;
  font-size: 12px;
}
.scheme-card p {
  margin: 0;
  color: #909399;
  font-size: 13px;
  line-height: 1.6;
}
@media (max-width: 1100px) {
  .hero-card,
  .flow-board {
    grid-template-columns: 1fr;
  }
  .hero-card {
    flex-direction: column;
  }
  .hero-actions {
    align-items: flex-start;
  }
}
</style>
