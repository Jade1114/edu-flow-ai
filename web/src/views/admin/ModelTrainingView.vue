<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request.js'
import { ElMessage } from 'element-plus'
import { Cpu, DataAnalysis, Refresh, TrendCharts, Finished, VideoPlay, CircleCheck, CircleClose } from '@element-plus/icons-vue'

// === 反馈数据 ===
const feedbackStats = ref(null)
const feedbackLoading = ref(false)
const eventSummary = ref(null)
const eventLoading = ref(false)

async function loadEventSummary(taskId) {
  eventLoading.value = true
  try {
    const params = taskId ? `?taskId=${taskId}&recentLimit=100` : '?recentLimit=100'
    eventSummary.value = await request.get(`/api/ml/feedback/events/summary${params}`)
  } catch (e) {
    eventSummary.value = null
  } finally {
    eventLoading.value = false
  }
}

async function loadLatestFeedbackJson(taskId) {
  feedbackLoading.value = true
  try {
    const params = taskId ? `?taskId=${taskId}` : ''
    feedbackStats.value = await request.get(`/api/ml/feedback/latest-export${params}`)
  } catch (e) {
    feedbackStats.value = null
  } finally {
    feedbackLoading.value = false
  }
}

async function generateFeedbackJson(taskId) {
  feedbackLoading.value = true
  try {
    const params = taskId ? `?taskId=${taskId}` : ''
    feedbackStats.value = await request.get(`/api/ml/feedback/export${params}`)
    loadEventSummary(taskId)
    ElMessage.success('反馈 JSON 已生成')
  } catch (e) {
    ElMessage.error('生成反馈 JSON 失败')
  } finally {
    feedbackLoading.value = false
  }
}

// === 训练操作 ===
const training = ref(false)
const trainResult = ref(null)

async function triggerRetrain(taskId) {
  training.value = true
  trainResult.value = { status: 'RUNNING', message: '正在将最新反馈 JSON 转为训练样本...' }
  try {
    const params = taskId ? `?taskId=${taskId}` : ''
    const result = await request.post(`/api/ml/feedback/train${params}`)
    trainResult.value = result
    if (result.status === 'SUCCEEDED') {
      ElMessage.success(`训练完成！${result.sampleCount || 0} 条样本`)
      loadTrainingLogs()
    } else {
      ElMessage.error(`训练失败: ${result.message}`)
    }
  } catch (e) {
    trainResult.value = { status: 'FAILED', message: e.message || '请求失败' }
    ElMessage.error('重训请求失败')
  } finally {
    training.value = false
  }
}

// === 训练历史 ===
const trainingLogs = ref([])
const logsLoading = ref(false)

async function loadTrainingLogs() {
  logsLoading.value = true
  try {
    trainingLogs.value = await request.get('/api/ml/feedback/training-logs?limit=20')
  } catch (e) {
    // 表可能还没数据，静默失败
    trainingLogs.value = []
  } finally {
    logsLoading.value = false
  }
}

// === 图表数据 ===
const positiveRate = computed(() => {
  if (!trainingLogs.value.length) return 0
  const last = trainingLogs.value[0]
  const total = (last.sampleCount || 1)
  return Math.round((last.positiveCount || 0) / total * 100)
})

function eventCount(type) {
  const row = eventSummary.value?.eventTypes?.find(item => item.eventType === type)
  return row?.eventCount || 0
}

function eventTypeLabel(type) {
  const map = {
    SCHEME_CONFIRMED: '方案确认',
    ITEM_MOVED: '片段移动',
    ITEM_MARKED_GOOD: '人工标好',
    ITEM_MARKED_BAD: '人工标差',
  }
  return map[type] || type || '-'
}

const eventCards = computed(() => [
  { label: '事件总数', value: eventSummary.value?.eventCount || 0, type: 'primary' },
  { label: '方案确认', value: eventCount('SCHEME_CONFIRMED'), type: 'success' },
  { label: '片段移动', value: eventCount('ITEM_MOVED'), type: 'warning' },
  { label: '人工标注', value: eventCount('ITEM_MARKED_GOOD') + eventCount('ITEM_MARKED_BAD'), type: 'danger' },
])

// 趋势图与分布
const chartWidth = 400

const aucPoints = computed(() =>
  [...trainingLogs.value].reverse().map(r => {
    const v = validationMetrics(r)
    return r.evalAuc ?? v?.auc ?? null
  }).filter(v => v != null)
)

const sepPoints = computed(() =>
  [...trainingLogs.value].reverse().map(r => {
    const v = validationMetrics(r)
    return r.evalAccuracy ?? v?.score_separation ?? null
  }).filter(v => v != null)
)

const latestScoreDist = computed(() => {
  const last = trainingLogs.value[0]
  if (!last) return []
  return valScoreDistribution(last) || []
})

const statsCards = computed(() => {
  const last = trainingLogs.value[0]
  if (!last) return []
  const metrics = trainingMetrics(last)
  const valMetrics = validationMetrics(last)
  return [
    { label: '模型版本', value: last.modelVersion || '-', icon: Cpu },
    { label: '训练类型', value: typeLabel(last.trainingType), icon: VideoPlay },
    { label: '样本总数', value: last.sampleCount || 0, icon: DataAnalysis },
    { label: '正样本率', value: positiveRate.value + '%', icon: CircleCheck },
    { label: 'AUC', value: last.evalAuc != null ? last.evalAuc.toFixed(4) : (valMetrics?.auc != null ? valMetrics.auc.toFixed(4) : '-'), icon: TrendCharts },
    { label: '评分分离度', value: last.evalAccuracy != null ? last.evalAccuracy.toFixed(4) : (valMetrics?.score_separation != null ? valMetrics.score_separation.toFixed(4) : '-'), icon: Finished },
  ]
})

function parseMetricsJson(row) {
  if (!row?.metricsJson) return null
  try {
    return JSON.parse(row.metricsJson)
  } catch (e) {
    return null
  }
}

function trainingMetrics(row) {
  return parseMetricsJson(row)?.metrics || null
}

function validationMetrics(row) {
  return parseMetricsJson(row)?.validation || null
}

function valScoreDistribution(row) {
  return validationMetrics(row)?.score_distribution || null
}

function modelParams(row) {
  const payload = parseMetricsJson(row)
  if (!payload?.model_params) return '-'
  return Object.entries(payload.model_params)
    .map(([key, value]) => `${key}=${value}`)
    .join(', ')
}

function comparisonLabel(row) {
  const comparison = parseMetricsJson(row)?.comparison
  if (!comparison) return '-'
  return comparison.baseline_type === 'PREVIOUS_FEEDBACK' ? '上次反馈模型' : '初始模型'
}

function previousModelPath(row) {
  return parseMetricsJson(row)?.comparison?.previous_model_path || ''
}

function shortPath(path) {
  if (!path) return '-'
  const index = path.indexOf('/server/')
  return index >= 0 ? path.substring(index + 1) : path
}

function typeLabel(type) {
  const map = { INITIAL: '初始训练', FEEDBACK: '反馈重训', FULL: '全量训练' }
  return map[type] || type || '-'
}

function statusTag(status) {
  const map = { SUCCEEDED: 'success', FAILED: 'danger', RUNNING: 'warning' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { SUCCEEDED: '成功', FAILED: '失败', RUNNING: '运行中' }
  return map[status] || status
}

function fmtTime(t) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadLatestFeedbackJson()
  loadEventSummary()
  loadTrainingLogs()
})
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 16px">
    <!-- 顶部标题 -->
    <div style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <h2 style="margin: 0">模型训练中心</h2>
        <p style="margin: 4px 0 0; color: #909399; font-size: 13px">
          反馈事件 → 样本构造 → LightGBM 重训 → 模型版本更新
        </p>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button :icon="Refresh" @click="loadEventSummary()" :loading="eventLoading">
          刷新事件
        </el-button>
        <el-button :icon="Refresh" @click="generateFeedbackJson()" :loading="feedbackLoading">
          生成反馈 JSON
        </el-button>
        <el-button type="warning" @click="triggerRetrain()" :loading="training" :disabled="training || !feedbackStats?.exportPath">
          {{ training ? '训练中...' : '重训模型' }}
        </el-button>
      </div>
    </div>

    <!-- 训练状态提示 -->
    <el-alert
      v-if="trainResult"
      :type="trainResult.status === 'SUCCEEDED' ? 'success' : trainResult.status === 'FAILED' ? 'error' : 'warning'"
      :title="trainResult.status === 'SUCCEEDED'
        ? `训练完成 · ${trainResult.sampleCount || 0} 条样本已生成 · 模型已更新为 ${trainResult.modelPath || '最新版本'}`
        : trainResult.status === 'FAILED'
          ? `训练失败: ${trainResult.message}`
          : `训练中: ${trainResult.message}`"
      show-icon
      :closable="false"
    />

    <!-- 最新模型卡片 -->
    <el-row :gutter="16" v-if="statsCards.length">
      <el-col :span="4" v-for="card in statsCards" :key="card.label">
        <el-card shadow="hover" :body-style="{ padding: '16px' }">
          <div style="display: flex; align-items: center; gap: 10px">
            <el-icon :size="24" color="#409eff"><component :is="card.icon" /></el-icon>
            <div>
              <div style="font-size: 12px; color: #909399">{{ card.label }}</div>
              <div style="font-size: 20px; font-weight: 700; color: #303133">{{ card.value }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 空状态 -->
    <el-empty v-if="!statsCards.length && !training" description="还没有训练记录，请先创建排课任务并生成方案，积累反馈数据后再开始重训" />

    <!-- 反馈事件采集台账 -->
    <el-card shadow="never">
      <template #header>
        <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
          <el-icon><DataAnalysis /></el-icon>
          <span>反馈事件采集台账</span>
          <el-tag size="small" type="info" style="margin-left: auto">
            确认/调整/人工标注自动采集
          </el-tag>
        </div>
      </template>
      <el-row :gutter="12" v-loading="eventLoading">
        <el-col :span="6" v-for="card in eventCards" :key="card.label">
          <div class="stat-card">
            <div class="stat-num" :class="`stat-${card.type}`">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </el-col>
      </el-row>
      <el-table
        :data="eventSummary?.eventTypes || []"
        size="small"
        border
        style="width: 100%; margin-top: 12px"
        empty-text="暂无反馈事件"
      >
        <el-table-column label="事件类型" min-width="160">
          <template #default="{ row }">{{ eventTypeLabel(row.eventType) }}</template>
        </el-table-column>
        <el-table-column prop="eventCount" label="事件数" width="90" align="center" />
      </el-table>
      <el-table
        :data="eventSummary?.recentEvents || []"
        size="small"
        border
        style="width: 100%; margin-top: 12px"
        empty-text="暂无行为事件"
      >
        <el-table-column prop="id" label="事件ID" width="80" align="center" />
        <el-table-column prop="taskId" label="任务" width="80" align="center" />
        <el-table-column label="行为类型" min-width="130">
          <template #default="{ row }">{{ eventTypeLabel(row.eventType) }}</template>
        </el-table-column>
        <el-table-column prop="schemeId" label="方案" width="80" align="center" />
        <el-table-column prop="itemId" label="片段" width="80" align="center" />
        <el-table-column prop="teachingTaskId" label="教学任务" width="90" align="center" />
        <el-table-column prop="reasonCode" label="原因码" width="140" show-overflow-tooltip />
        <el-table-column prop="reasonText" label="说明" min-width="180" show-overflow-tooltip />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.createdAt) }}</template>
        </el-table-column>
      </el-table>
      <div style="font-size: 12px; color: #909399; margin-top: 10px; line-height: 1.7">
        当前阶段先沉淀原始反馈事件，不直接把未选候选当负样本。后续样本构造器会按优先级和移动相消规则把事件转成训练样本。
      </div>
    </el-card>

    <!-- 反馈数据 & 操作 -->
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
              <el-icon><DataAnalysis /></el-icon>
              <span>可用于训练的数据</span>
              <el-tag v-if="feedbackStats" size="small" type="info" style="margin-left: auto">
                {{ feedbackStats.exportPath ? '已导出' : '待导出' }}
              </el-tag>
            </div>
          </template>
          <div v-if="feedbackStats" style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; text-align: center">
            <div class="stat-card">
              <div class="stat-num">{{ feedbackStats.schemeCount }}</div>
              <div class="stat-label">候选方案</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ feedbackStats.itemCount }}</div>
              <div class="stat-label">排课明细</div>
            </div>
            <div class="stat-card">
              <div class="stat-num" style="color: #67c23a">{{ feedbackStats.feedbackCount }}</div>
              <div class="stat-label">确认反馈</div>
            </div>
            <div class="stat-card">
              <div class="stat-num" style="color: #e6a23c">{{ feedbackStats.adjustmentCount }}</div>
              <div class="stat-label">人工调整</div>
            </div>
            <div class="stat-card">
              <div class="stat-num" style="color: #f56c6c">{{ feedbackStats.conflictCount }}</div>
              <div class="stat-label">冲突记录</div>
            </div>
            <div class="stat-card">
              <div class="stat-num" style="color: #409eff">{{ feedbackStats.eventCount || 0 }}</div>
              <div class="stat-label">反馈事件</div>
            </div>
          </div>
          <div v-else style="text-align: center; padding: 32px; color: #909399">
            点击“生成反馈 JSON”后查看本次导出的反馈数据统计
          </div>

          <!-- 标签策略说明 -->
          <el-divider />
          <div style="font-size: 12px; color: #909399; line-height: 1.8">
            <strong>标签策略：</strong>
            先记录方案确认、片段移动和人工标注事件；真正的正负样本由后续样本构造器统一生成，避免把未选候选误判成负样本。
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never" :body-style="{ padding: '20px' }">
          <template #header>
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
              <el-icon><TrendCharts /></el-icon>
              <span>训练样本构成</span>
            </div>
          </template>
          <div v-if="trainingLogs.length" style="text-align: center">
            <div style="font-size: 48px; font-weight: 700; color: #303133; line-height: 1.2">
              {{ trainingLogs[0]?.sampleCount || 0 }}
            </div>
            <div style="color: #909399; margin-bottom: 16px">最近训练样本总数</div>
            <div style="display: flex; gap: 12px; justify-content: center">
              <el-tag type="success" size="large">正样本 {{ trainingLogs[0]?.positiveCount || 0 }}</el-tag>
              <el-tag type="danger" size="large">负样本 {{ trainingLogs[0]?.negativeCount || 0 }}</el-tag>
            </div>
            <div style="margin-top: 16px">
              <div style="height: 8px; border-radius: 4px; background: #f0f0f0; overflow: hidden">
                <div :style="{
                  height: '100%',
                  width: positiveRate + '%',
                  background: 'linear-gradient(90deg, #67c23a, #409eff)',
                  borderRadius: '4px',
                  transition: 'width 0.5s ease'
                }" />
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 11px; color: #909399; margin-top: 4px">
                <span>正 {{ positiveRate }}%</span>
                <span>负 {{ 100 - positiveRate }}%</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无训练数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 验证指标趋势 -->
    <el-row :gutter="16" v-if="trainingLogs.length">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
              <el-icon><TrendCharts /></el-icon>
              <span>验证指标趋势（AUC / 分离度）</span>
            </div>
          </template>
          <div style="height: 180px; position: relative; padding: 10px 0">
            <svg :viewBox="`0 0 ${chartWidth} 160`" style="width: 100%; height: 160px">
              <!-- 网格线 -->
              <line v-for="gy in [0, 0.25, 0.5, 0.75, 1.0]" :key="gy" :x1="20" :x2="chartWidth - 10" :y1="160 - gy * 150" :y2="160 - gy * 150" stroke="#f0f0f0" stroke-width="1" />
              <!-- AUC 线 -->
              <polyline v-if="aucPoints.length >= 2"
                :points="aucPoints.map((p, i) => `${20 + i * (chartWidth - 30) / Math.max(aucPoints.length - 1, 1)},${160 - p * 150}`).join(' ')"
                fill="none" stroke="#409eff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              <!-- 分离度线 -->
              <polyline v-if="sepPoints.length >= 2"
                :points="sepPoints.map((p, i) => `${20 + i * (chartWidth - 30) / Math.max(sepPoints.length - 1, 1)},${150 - Math.min(p * 150, 150)}`).join(' ')"
                fill="none" stroke="#67c23a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4,2" />
              <!-- 图例 -->
              <text x="20" y="18" font-size="11" fill="#409eff">AUC</text>
              <text x="80" y="18" font-size="11" fill="#67c23a">分离度</text>
            </svg>
          </div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
              <el-icon><DataAnalysis /></el-icon>
              <span>最新评分分布</span>
            </div>
          </template>
          <div v-if="latestScoreDist.length" style="display: flex; flex-direction: column; gap: 6px; padding: 8px 0">
            <div v-for="bucket in latestScoreDist" :key="bucket.range" style="display: flex; align-items: center; gap: 8px; font-size: 12px">
              <span style="width: 70px; color: #909399; text-align: right">{{ bucket.range }}</span>
              <div style="flex: 1; height: 18px; background: #f0f0f0; border-radius: 3px; overflow: hidden">
                <div :style="{
                  height: '100%',
                  width: bucket.pct + '%',
                  background: bucket.range.includes('0.99') || bucket.range.includes('0.999') ? '#f56c6c' : '#409eff',
                  borderRadius: '3px',
                  transition: 'width 0.5s ease'
                }" />
              </div>
              <span style="width: 40px; color: #606266">{{ bucket.count }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无评分分布数据，训练一次后即可查看" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 训练历史 -->
    <el-card shadow="never">
      <template #header>
        <div style="display: flex; align-items: center; gap: 6px; font-weight: 700">
          <el-icon><Finished /></el-icon>
          <span>训练历史</span>
        </div>
      </template>
      <el-table :data="trainingLogs" border size="small" v-loading="logsLoading" empty-text="暂无训练记录">
        <el-table-column prop="modelVersion" label="版本" width="80" />
        <el-table-column prop="trainingType" label="类型" width="90">
          <template #default="{ row }">{{ typeLabel(row.trainingType) }}</template>
        </el-table-column>
        <el-table-column prop="sampleCount" label="样本" width="70" />
        <el-table-column prop="positiveCount" label="正样本" width="70" />
        <el-table-column prop="negativeCount" label="负样本" width="70" />
        <el-table-column label="AUC" width="80">
          <template #default="{ row }">
            <span v-if="row.evalAuc != null" :style="{ color: row.evalAuc >= 0.7 ? '#67c23a' : row.evalAuc >= 0.5 ? '#e6a23c' : '#f56c6c' }">
              {{ row.evalAuc.toFixed(4) }}
            </span>
            <span v-else>{{ validationMetrics(row)?.auc != null ? validationMetrics(row).auc.toFixed(4) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分离度" width="80">
          <template #default="{ row }">
            <span v-if="row.evalAccuracy != null" :style="{ color: row.evalAccuracy > 0.1 ? '#67c23a' : row.evalAccuracy > 0.02 ? '#e6a23c' : '#909399' }">
              {{ row.evalAccuracy.toFixed(4) }}
            </span>
            <span v-else>{{ validationMetrics(row)?.score_separation != null ? validationMetrics(row).score_separation.toFixed(4) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="评分标准差" width="90">
          <template #default="{ row }">
            {{ validationMetrics(row)?.score_std != null ? validationMetrics(row).score_std.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="对比基线" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span :title="shortPath(previousModelPath(row))">{{ comparisonLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模型文件" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ shortPath(row.modelPath) }}</template>
        </el-table-column>
        <el-table-column label="训练参数" width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ modelParams(row) }}</template>
        </el-table-column>
        <el-table-column prop="schemeCount" label="方案" width="60" />
        <el-table-column prop="feedbackCount" label="反馈" width="60" />
        <el-table-column prop="adjustmentCount" label="调整" width="60" />
        <el-table-column prop="conflictCount" label="冲突" width="60" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trainStartedAt" label="训练时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.trainStartedAt) }}</template>
        </el-table-column>
        <el-table-column prop="errorMessage" label="备注" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.stat-card {
  padding: 12px 8px;
  border-radius: 10px;
  background: #f8fafc;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}
.stat-primary {
  color: #409eff;
}
.stat-success {
  color: #67c23a;
}
.stat-danger {
  color: #f56c6c;
}
.stat-warning {
  color: #e6a23c;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
