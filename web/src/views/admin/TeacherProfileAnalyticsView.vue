<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

type RateMap = Record<string, number>

type FeedbackEventCounts = Record<string, number>

interface FeedbackEvidenceSummary {
  event_counts?: FeedbackEventCounts
  positive_weight?: number
  negative_weight?: number
  positive_weekdays?: RateMap
  negative_weekdays?: RateMap
  positive_periods?: RateMap
  negative_periods?: RateMap
}

interface TeacherProfile {
  teacher_id: number | null
  teacher_name: string
  observation_count: number
  declared_profile?: {
    profile_note?: string
    availability_matrix_json?: string
    summary?: string
    preference?: Record<string, unknown>
  }
  feedback_profile?: Record<string, unknown>
  feedback_evidence_summary?: FeedbackEvidenceSummary
  feedback_confidence?: number
  derived_from_data: {
    early_period_rate: number
    late_period_rate: number
    weekday_rates: RateMap
    period_rates: RateMap
    preferred_weekdays: number[]
    common_periods: number[]
    avg_daily_lessons: number
    max_observed_daily_lessons: number
    p90_daily_lessons: number
    avg_weekly_active_days: number
    compactness_score: number
    room_type_rates: RateMap
    common_room_types: string[]
  }
  final_profile: {
    avoid_early_period: boolean
    avoid_late_period: boolean
    prefer_compact_schedule: boolean
    preferred_weekdays: number[]
    preferred_periods: number[]
    max_daily_lessons: number
    preferred_room_types: string[]
  }
}

interface TeacherProfileDoc {
  profile_version: string
  generated_at: string
  teacher_count: number
  declared_profile_count?: number
  feedback_profile_count?: number
  feedback_merge_strategy?: string
  merge_strategy?: string
  profiles: TeacherProfile[]
}

interface TeacherSatisfactionReport {
  report_version: string
  generated_at: string
  scheme_count: number
  schemes: SchemeSatisfactionReport[]
}

interface SchemeSatisfactionReport {
  scheme_index: number
  item_count: number
  profiled_teacher_count: number
  summary: {
    avg_satisfaction_score: number
    teacher_count: number
    low_satisfaction_count: number
    hard_unavailable_violation_count: number
    note?: string
  }
  low_satisfaction_teachers: TeacherSatisfactionRow[]
  teacher_reports: TeacherSatisfactionRow[]
}

interface TeacherSatisfactionRow {
  teacher_id: number | null
  teacher_name: string
  item_count: number
  satisfaction_score: number
  components: Record<string, number>
  evidence: Record<string, number | null>
  profile_used: Record<string, unknown>
}

const router = useRouter()
const loading = ref(false)
const reportLoading = ref(false)
const profileDoc = ref<TeacherProfileDoc | null>(null)
const satisfactionReport = ref<TeacherSatisfactionReport | null>(null)
const keyword = ref('')
const declaredFilter = ref('all')
const feedbackFilter = ref('all')
const satisfactionFilter = ref('all')
const tagFilter = ref('all')
const selectedProfile = ref<TeacherProfile | null>(null)
const selectedTeacherReport = ref<TeacherSatisfactionRow | null>(null)
const detailVisible = ref(false)
const reportDetailVisible = ref(false)

const profiles = computed(() => profileDoc.value?.profiles || [])
const latestSchemeReport = computed(() => satisfactionReport.value?.schemes?.[0] || null)
const satisfactionSummary = computed(() => latestSchemeReport.value?.summary || null)
const lowSatisfactionTeachers = computed(() => latestSchemeReport.value?.low_satisfaction_teachers || [])
const lowSatisfactionTeacherNames = computed(() => new Set(lowSatisfactionTeachers.value.map((item) => item.teacher_name)))

const filteredProfiles = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return profiles.value.filter((profile) => {
    const matchText = !text || String(profile.teacher_id || '').includes(text) || profile.teacher_name.toLowerCase().includes(text)
    const matchDeclared =
      declaredFilter.value === 'all' ||
      (declaredFilter.value === 'declared' && !!profile.declared_profile) ||
      (declaredFilter.value === 'derived' && !profile.declared_profile)
    const matchFeedback =
      feedbackFilter.value === 'all' ||
      (feedbackFilter.value === 'feedback' && hasFeedbackProfile(profile)) ||
      (feedbackFilter.value === 'no_feedback' && !hasFeedbackProfile(profile))
    const matchSatisfaction =
      satisfactionFilter.value === 'all' ||
      (satisfactionFilter.value === 'low' && lowSatisfactionTeacherNames.value.has(profile.teacher_name))
    const matchTag =
      tagFilter.value === 'all' ||
      (tagFilter.value === 'avoid_early' && profile.final_profile.avoid_early_period) ||
      (tagFilter.value === 'compact' && profile.final_profile.prefer_compact_schedule) ||
      (tagFilter.value === 'avoid_late' && profile.final_profile.avoid_late_period)
    return matchText && matchDeclared && matchFeedback && matchSatisfaction && matchTag
  })
})

const summaryCards = computed(() => {
  const rows = profiles.value
  if (!rows.length) return []
  const avoidEarly = rows.filter((p) => p.final_profile.avoid_early_period).length
  const compact = rows.filter((p) => p.final_profile.prefer_compact_schedule).length
  const feedbackCount = rows.filter(hasFeedbackProfile).length
  const avgEarlyRate = avg(rows.map((p) => p.derived_from_data.early_period_rate))
  const avgCompact = avg(rows.map((p) => p.derived_from_data.compactness_score))
  return [
    { label: '画像教师数', value: rows.length, suffix: '人' },
    { label: '教师声明画像', value: profileDoc.value?.declared_profile_count || 0, suffix: '人' },
    { label: '反馈画像证据', value: profileDoc.value?.feedback_profile_count || feedbackCount, suffix: '人' },
    { label: '低早课倾向', value: avoidEarly, suffix: '人' },
    { label: '偏好紧凑排课', value: compact, suffix: '人' },
    { label: '平均第1节占比', value: percent(avgEarlyRate), suffix: '' },
    { label: '平均紧凑度', value: percent(avgCompact), suffix: '' },
  ]
})

async function loadProfiles() {
  loading.value = true
  try {
    profileDoc.value = await request.get<TeacherProfileDoc>('/api/ml/teacher-profiles/v3')
    if (!selectedProfile.value && profiles.value.length) {
      selectedProfile.value = profiles.value[0]
    }
  } catch (error) {
    profileDoc.value = null
    ElMessage.warning('暂未读取到 V3 教师画像，请先运行画像生成脚本')
  } finally {
    loading.value = false
  }
}

async function loadSatisfactionReport() {
  reportLoading.value = true
  try {
    satisfactionReport.value = await request.get<TeacherSatisfactionReport>('/api/ml/teacher-profiles/v3/satisfaction/latest')
  } catch (error) {
    satisfactionReport.value = null
  } finally {
    reportLoading.value = false
  }
}

function openDetail(profile: TeacherProfile) {
  selectedProfile.value = profile
  detailVisible.value = true
}

function openReportDetail(report: TeacherSatisfactionRow) {
  selectedTeacherReport.value = report
  reportDetailVisible.value = true
}

function editTeacherProfile(profile: TeacherProfile) {
  if (!profile.teacher_id) {
    ElMessage.warning('该教师没有可跳转的 ID')
    return
  }
  router.push({
    path: `/admin/teachers/${profile.teacher_id}`,
    query: { from: '/admin/teacher-profiles', section: 'profile' },
  })
}

function avg(values: number[]) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + Number(value || 0), 0) / values.length
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

function weekdayLabel(day: number) {
  return ['-', '周一', '周二', '周三', '周四', '周五', '周六', '周日'][day] || `周${day}`
}

function periodLabel(period: number) {
  return `第${period}节`
}

function rateEntries(rates: RateMap, labeler: (value: number) => string) {
  return Object.entries(rates || {})
    .map(([key, value]) => ({ label: labeler(Number(key)), value: Number(value || 0) }))
    .sort((a, b) => b.value - a.value)
}

function topRateText(rates: RateMap, labeler: (value: number) => string) {
  const first = rateEntries(rates, labeler)[0]
  if (!first) return '-'
  return `${first.label} ${percent(first.value)}`
}

function hasFeedbackProfile(profile: TeacherProfile) {
  return !!profile.feedback_evidence_summary && Object.keys(profile.feedback_evidence_summary.event_counts || {}).length > 0
}

function feedbackEventTotal(profile: TeacherProfile) {
  return Object.values(profile.feedback_evidence_summary?.event_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
}

function feedbackConfidenceText(profile: TeacherProfile) {
  const confidence = Number(profile.feedback_confidence || 0)
  return `${Math.round(confidence * 100)}%`
}

function feedbackEventEntries(profile: TeacherProfile) {
  return Object.entries(profile.feedback_evidence_summary?.event_counts || {})
    .map(([key, value]) => ({ key, label: feedbackEventLabel(key), value: Number(value || 0) }))
    .sort((a, b) => b.value - a.value)
}

function feedbackEventLabel(key: string) {
  const map: Record<string, string> = {
    SCHEME_CONFIRMED: '方案确认',
    ITEM_MOVED: '人工调整',
    ITEM_MARKED_GOOD: '标为可参考',
    ITEM_MARKED_BAD: '标为不满意',
    ADJUSTMENT_APPROVED: '调课通过',
    ADJUSTMENT_REJECTED: '调课驳回',
  }
  return map[key] || key
}

function feedbackProfileTags(profile: TeacherProfile) {
  const feedback = profile.feedback_profile || {}
  const tags = []
  if (feedback.avoid_early_period) tags.push({ label: '反馈：避开第1节', type: 'warning' })
  if (feedback.avoid_late_period) tags.push({ label: '反馈：避开晚课', type: 'warning' })
  const weekdays = Array.isArray(feedback.preferred_weekdays) ? feedback.preferred_weekdays : []
  const periods = Array.isArray(feedback.preferred_periods) ? feedback.preferred_periods : []
  weekdays.forEach((day) => tags.push({ label: `反馈偏好 ${weekdayLabel(Number(day))}`, type: 'primary' }))
  periods.forEach((period) => tags.push({ label: `反馈偏好 ${periodLabel(Number(period))}`, type: 'primary' }))
  return tags
}

function profileTags(profile: TeacherProfile) {
  const tags = []
  if (profile.final_profile.avoid_early_period) tags.push({ label: '避开第1节', type: 'warning' })
  if (profile.final_profile.avoid_late_period) tags.push({ label: '避开晚课', type: 'warning' })
  if (profile.final_profile.prefer_compact_schedule) tags.push({ label: '偏好紧凑', type: 'success' })
  if (profile.final_profile.max_daily_lessons) tags.push({ label: `日上限 ${profile.final_profile.max_daily_lessons}`, type: 'info' })
  return tags
}

function scoreType(score: number) {
  if (score >= 0.85) return 'success'
  if (score >= 0.7) return 'warning'
  return 'danger'
}

function componentLabel(key: string) {
  const map: Record<string, string> = {
    early_period: '第1节避让',
    late_period: '晚课避让',
    preferred_weekday: '偏好星期',
    preferred_period: '常见节次',
    daily_load: '单日负载',
    room_type: '教室类型',
  }
  return map[key] || key
}

function componentEntries(components: Record<string, number>) {
  return Object.entries(components || {}).map(([key, value]) => ({ key, label: componentLabel(key), value }))
}

onMounted(() => {
  loadProfiles()
  loadSatisfactionReport()
})
</script>

<template>
  <div class="teacher-profile-page">
    <el-card class="page-card" v-loading="loading">
      <template #header>
        <div class="page-header">
          <div>
            <div class="title">教师画像分析</div>
            <div class="subtitle">从真实课表提取教师行为画像，先用于可视化与课表满足度分析</div>
          </div>
          <el-button :icon="Refresh" @click="loadProfiles">刷新</el-button>
        </div>
      </template>

      <el-empty v-if="!loading && !profileDoc" description="暂无 V3 教师画像数据" />

      <template v-else-if="profileDoc">
        <div class="meta-row">
          <el-tag type="primary">{{ profileDoc.profile_version }}</el-tag>
          <span>生成时间：{{ profileDoc.generated_at }}</span>
        </div>

        <div class="summary-grid">
          <div v-for="card in summaryCards" :key="card.label" class="summary-card">
            <div class="summary-value">{{ card.value }}{{ card.suffix }}</div>
            <div class="summary-label">{{ card.label }}</div>
          </div>
        </div>

        <el-card class="satisfaction-card" shadow="never" v-loading="reportLoading">
          <template #header>
            <div class="section-header">
              <div>
                <div class="section-heading">课表画像满足度</div>
                <div class="section-subtitle">分析最新生成方案对教师画像的满足情况</div>
              </div>
              <el-button size="small" @click="loadSatisfactionReport">刷新报告</el-button>
            </div>
          </template>

          <el-empty v-if="!reportLoading && !satisfactionSummary" description="暂无课表满足度报告" />
          <template v-else-if="satisfactionSummary">
            <div class="report-summary-grid">
              <div class="report-metric primary">
                <span>平均满足度</span>
                <b>{{ percent(satisfactionSummary.avg_satisfaction_score) }}</b>
              </div>
              <div class="report-metric">
                <span>覆盖教师</span>
                <b>{{ satisfactionSummary.teacher_count }} 人</b>
              </div>
              <div class="report-metric danger">
                <span>低满足教师</span>
                <b>{{ satisfactionSummary.low_satisfaction_count }} 人</b>
              </div>
              <div class="report-metric">
                <span>硬约束冲突</span>
                <b>{{ satisfactionSummary.hard_unavailable_violation_count }}</b>
              </div>
            </div>

            <div class="low-teacher-list">
              <div class="low-teacher-title">低满足教师 Top 10</div>
              <el-table :data="lowSatisfactionTeachers" size="small" max-height="320">
                <el-table-column prop="teacher_name" label="教师" width="110" />
                <el-table-column prop="item_count" label="课时" width="70" />
                <el-table-column label="满足度" width="120">
                  <template #default="{ row }">
                    <el-tag :type="scoreType(row.satisfaction_score) as any">
                      {{ percent(row.satisfaction_score) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="主要短板">
                  <template #default="{ row }">
                    <div class="component-tags">
                      <el-tag
                        v-for="item in componentEntries(row.components).filter((c) => c.value < 0.7)"
                        :key="item.key"
                        size="small"
                        type="warning"
                      >
                        {{ item.label }} {{ percent(item.value) }}
                      </el-tag>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="90">
                  <template #default="{ row }">
                    <el-button size="small" link type="primary" @click="openReportDetail(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-card>

        <div class="toolbar">
          <div class="filter-row">
            <el-input
              v-model="keyword"
              class="search-input"
              :prefix-icon="Search"
              placeholder="按教师姓名或 ID 搜索"
              clearable
            />
            <el-select v-model="declaredFilter" class="filter-select" placeholder="声明状态">
              <el-option label="全部画像" value="all" />
              <el-option label="有教师声明" value="declared" />
              <el-option label="仅历史推断" value="derived" />
            </el-select>
            <el-select v-model="feedbackFilter" class="filter-select" placeholder="反馈证据">
              <el-option label="全部反馈" value="all" />
              <el-option label="有反馈证据" value="feedback" />
              <el-option label="暂无反馈" value="no_feedback" />
            </el-select>
            <el-select v-model="satisfactionFilter" class="filter-select" placeholder="满足度">
              <el-option label="全部满足度" value="all" />
              <el-option label="低满足教师" value="low" />
            </el-select>
            <el-select v-model="tagFilter" class="filter-select" placeholder="画像标签">
              <el-option label="全部标签" value="all" />
              <el-option label="避开第1节" value="avoid_early" />
              <el-option label="避开晚课" value="avoid_late" />
              <el-option label="偏好紧凑" value="compact" />
            </el-select>
          </div>
          <span class="result-count">当前 {{ filteredProfiles.length }} / {{ profiles.length }} 人</span>
        </div>

        <div class="profile-grid">
          <el-card
            v-for="profile in filteredProfiles"
            :key="profile.teacher_id || profile.teacher_name"
            class="profile-card"
            shadow="hover"
            @click="openDetail(profile)"
          >
            <div class="profile-card-header">
              <div>
                <div class="teacher-name">{{ profile.teacher_name }}</div>
                <div class="teacher-id">ID: {{ profile.teacher_id || '-' }}</div>
              </div>
              <div class="profile-badges">
                <el-tag v-if="profile.declared_profile" size="small" type="success">有声明</el-tag>
                <el-tag v-if="hasFeedbackProfile(profile)" size="small" type="primary">
                  反馈 {{ feedbackConfidenceText(profile) }}
                </el-tag>
                <el-tag size="small">{{ profile.observation_count }} 条</el-tag>
              </div>
            </div>

            <div class="mini-stats">
              <div>
                <span>第1节占比</span>
                <b>{{ percent(profile.derived_from_data.early_period_rate) }}</b>
              </div>
              <div>
                <span>紧凑度</span>
                <b>{{ percent(profile.derived_from_data.compactness_score) }}</b>
              </div>
              <div>
                <span>常见星期</span>
                <b>{{ topRateText(profile.derived_from_data.weekday_rates, weekdayLabel) }}</b>
              </div>
              <div>
                <span>常见节次</span>
                <b>{{ topRateText(profile.derived_from_data.period_rates, periodLabel) }}</b>
              </div>
            </div>

            <div class="tag-row">
              <el-tag
                v-for="tag in profileTags(profile)"
                :key="tag.label"
                :type="tag.type as any"
                size="small"
              >
                {{ tag.label }}
              </el-tag>
            </div>
          </el-card>
        </div>
      </template>
    </el-card>

    <el-dialog v-model="detailVisible" width="720px" title="教师画像详情">
      <template v-if="selectedProfile">
        <div class="detail-title">
          <span>{{ selectedProfile.teacher_name }}</span>
          <el-tag>ID: {{ selectedProfile.teacher_id || '-' }}</el-tag>
          <el-button size="small" type="primary" plain @click="editTeacherProfile(selectedProfile)">编辑画像</el-button>
        </div>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="历史样本数">{{ selectedProfile.observation_count }}</el-descriptions-item>
          <el-descriptions-item label="平均单日课时">{{ selectedProfile.derived_from_data.avg_daily_lessons }}</el-descriptions-item>
          <el-descriptions-item label="最大单日课时">{{ selectedProfile.derived_from_data.max_observed_daily_lessons }}</el-descriptions-item>
          <el-descriptions-item label="建议日课时上限">{{ selectedProfile.final_profile.max_daily_lessons }}</el-descriptions-item>
          <el-descriptions-item label="平均周活跃天数">{{ selectedProfile.derived_from_data.avg_weekly_active_days }}</el-descriptions-item>
          <el-descriptions-item label="紧凑度">{{ percent(selectedProfile.derived_from_data.compactness_score) }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">最终画像</div>
        <div class="tag-row large">
          <el-tag v-for="tag in profileTags(selectedProfile)" :key="tag.label" :type="tag.type as any">
            {{ tag.label }}
          </el-tag>
          <el-tag v-for="day in selectedProfile.final_profile.preferred_weekdays" :key="`d-${day}`" type="primary">
            偏好 {{ weekdayLabel(day) }}
          </el-tag>
          <el-tag v-for="period in selectedProfile.final_profile.preferred_periods" :key="`p-${period}`" type="primary">
            常见 {{ periodLabel(period) }}
          </el-tag>
          <el-tag v-for="room in selectedProfile.final_profile.preferred_room_types" :key="room" type="info">
            {{ room }}
          </el-tag>
        </div>

        <div v-if="selectedProfile.declared_profile" class="declared-box">
          <div class="section-title">教师声明画像</div>
          <div class="declared-summary">{{ selectedProfile.declared_profile.summary || '教师声明偏好已合并进最终画像' }}</div>
          <div v-if="selectedProfile.declared_profile.profile_note" class="declared-note">
            {{ selectedProfile.declared_profile.profile_note }}
          </div>
        </div>

        <div v-if="hasFeedbackProfile(selectedProfile)" class="feedback-box">
          <div class="section-title">反馈画像证据</div>
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="事件数量">{{ feedbackEventTotal(selectedProfile) }}</el-descriptions-item>
            <el-descriptions-item label="置信度">{{ feedbackConfidenceText(selectedProfile) }}</el-descriptions-item>
            <el-descriptions-item label="正/负权重">
              {{ selectedProfile.feedback_evidence_summary?.positive_weight || 0 }} /
              {{ selectedProfile.feedback_evidence_summary?.negative_weight || 0 }}
            </el-descriptions-item>
          </el-descriptions>
          <div class="feedback-section-subtitle">反馈来源</div>
          <div class="tag-row">
            <el-tag v-for="event in feedbackEventEntries(selectedProfile)" :key="event.key" size="small" type="info">
              {{ event.label }} × {{ event.value }}
            </el-tag>
          </div>
          <div v-if="feedbackProfileTags(selectedProfile).length" class="feedback-section-subtitle">反馈推断偏好</div>
          <div v-if="feedbackProfileTags(selectedProfile).length" class="tag-row">
            <el-tag
              v-for="tag in feedbackProfileTags(selectedProfile)"
              :key="tag.label"
              :type="tag.type as any"
              size="small"
            >
              {{ tag.label }}
            </el-tag>
          </div>
        </div>

        <div class="section-title">星期分布</div>
        <div class="bar-list">
          <div v-for="row in rateEntries(selectedProfile.derived_from_data.weekday_rates, weekdayLabel)" :key="row.label" class="bar-row">
            <span>{{ row.label }}</span>
            <el-progress :percentage="Math.round(row.value * 100)" :stroke-width="10" />
          </div>
        </div>

        <div class="section-title">节次分布</div>
        <div class="bar-list">
          <div v-for="row in rateEntries(selectedProfile.derived_from_data.period_rates, periodLabel)" :key="row.label" class="bar-row">
            <span>{{ row.label }}</span>
            <el-progress :percentage="Math.round(row.value * 100)" :stroke-width="10" />
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="reportDetailVisible" width="680px" title="教师课表满足度详情">
      <template v-if="selectedTeacherReport">
        <div class="detail-title">
          <span>{{ selectedTeacherReport.teacher_name }}</span>
          <el-tag :type="scoreType(selectedTeacherReport.satisfaction_score) as any">
            满足度 {{ percent(selectedTeacherReport.satisfaction_score) }}
          </el-tag>
        </div>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="教师 ID">{{ selectedTeacherReport.teacher_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="排课条目数">{{ selectedTeacherReport.item_count }}</el-descriptions-item>
          <el-descriptions-item label="第1节条目">{{ selectedTeacherReport.evidence.early_item_count ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="晚课条目">{{ selectedTeacherReport.evidence.late_item_count ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="偏好星期命中">{{ selectedTeacherReport.evidence.preferred_weekday_hits ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="常见节次命中">{{ selectedTeacherReport.evidence.preferred_period_hits ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="超负载天数">{{ selectedTeacherReport.evidence.overloaded_days ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="教室类型命中">{{ selectedTeacherReport.evidence.preferred_room_type_hits ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="section-title">分项满足度</div>
        <div class="bar-list">
          <div v-for="item in componentEntries(selectedTeacherReport.components)" :key="item.key" class="bar-row wide">
            <span>{{ item.label }}</span>
            <el-progress
              :percentage="Math.round(item.value * 100)"
              :stroke-width="12"
              :status="item.value >= 0.85 ? 'success' : item.value >= 0.7 ? undefined : 'exception'"
            />
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.teacher-profile-page {
  min-height: 100%;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.subtitle {
  margin-top: 6px;
  color: #909399;
  font-size: 13px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  color: #606266;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  padding: 16px;
  border-radius: 12px;
  background: #f5f8ff;
  border: 1px solid #e4ecff;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #315efb;
}

.summary-label {
  margin-top: 4px;
  color: #606266;
  font-size: 13px;
}

.satisfaction-card {
  margin-bottom: 18px;
  border-color: #e4ecff;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-heading {
  font-weight: 700;
  color: #303133;
}

.section-subtitle {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.report-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.report-metric {
  padding: 14px;
  border-radius: 10px;
  background: #fafafa;
  border: 1px solid #ebeef5;
}

.report-metric span {
  display: block;
  color: #909399;
  font-size: 12px;
  margin-bottom: 6px;
}

.report-metric b {
  font-size: 22px;
  color: #303133;
}

.report-metric.primary b {
  color: #315efb;
}

.report-metric.danger b {
  color: #f56c6c;
}

.low-teacher-title {
  font-weight: 700;
  color: #303133;
  margin-bottom: 10px;
}

.component-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: 280px;
}

.filter-select {
  width: 140px;
}

.result-count {
  color: #909399;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.profile-card {
  cursor: pointer;
}

.profile-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.teacher-name {
  font-weight: 700;
  font-size: 16px;
  color: #303133;
}

.teacher-id {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.profile-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.mini-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.mini-stats div {
  padding: 8px;
  border-radius: 8px;
  background: #fafafa;
}

.mini-stats span {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.mini-stats b {
  color: #303133;
  font-size: 13px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.tag-row.large {
  margin-bottom: 8px;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
}

.section-title {
  margin: 18px 0 10px;
  font-weight: 700;
  color: #303133;
}

.declared-box {
  margin-top: 16px;
  padding: 12px;
  border-radius: 10px;
  background: #f0f9eb;
  border: 1px solid #d9ecff;
}

.declared-summary {
  color: #303133;
  font-weight: 600;
  margin-bottom: 8px;
}

.declared-note {
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.feedback-box {
  margin-top: 16px;
  padding: 12px;
  border-radius: 10px;
  background: #f5f8ff;
  border: 1px solid #dce8ff;
}

.feedback-section-subtitle {
  margin-top: 12px;
  color: #606266;
  font-size: 13px;
  font-weight: 600;
}

.bar-list {
  display: grid;
  gap: 10px;
}

.bar-row {
  display: grid;
  grid-template-columns: 70px 1fr;
  align-items: center;
  gap: 12px;
}

.bar-row.wide {
  grid-template-columns: 90px 1fr;
}

.bar-row span {
  color: #606266;
  font-size: 13px;
}
</style>
