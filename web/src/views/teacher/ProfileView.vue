<script setup>
import { ref, onMounted, watch } from 'vue'
import request from '@/api/request.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const periods = ['第1节', '第2节', '第3节', '第4节', '第5节']
const defaultMatrix = () => Array.from({ length: 5 }, () => Array(7).fill(0))

const profile = ref({
  availabilityMatrix: defaultMatrix(),
  profileNote: '',
  profilePreferenceJson: '',
})
const parsedPreference = ref(null)
const parseInterpretation = ref('')
const loading = ref(false)
const parsing = ref(false)
const saving = ref(false)
const initialized = ref(false)

function normalizeMatrix(raw) {
  const matrix = Array.isArray(raw) ? raw : defaultMatrix()
  return Array.from({ length: 5 }, (_, periodIndex) =>
    Array.from({ length: 7 }, (_, weekdayIndex) => {
      const value = matrix?.[periodIndex]?.[weekdayIndex]
      return [-1, 0, 1].includes(value) ? value : 0
    }),
  )
}

function parseMatrix(json) {
  if (!json) return defaultMatrix()
  try {
    return normalizeMatrix(JSON.parse(json))
  } catch {
    return defaultMatrix()
  }
}

function parsePreferenceJson(json) {
  if (!json) return null
  try {
    return JSON.parse(json)
  } catch {
    return null
  }
}

function nextAvailabilityValue(value) {
  if (value === 0) return 1
  if (value === 1) return -1
  return 0
}

function toggleCell(periodIndex, weekdayIndex) {
  profile.value.availabilityMatrix[periodIndex][weekdayIndex] = nextAvailabilityValue(
    profile.value.availabilityMatrix[periodIndex][weekdayIndex],
  )
}

function cellClass(value) {
  return {
    'availability-cell': true,
    available: value === 1,
    unavailable: value === -1,
  }
}

function cellText(value) {
  if (value === 1) return '可用'
  if (value === -1) return '不可用'
  return '随意'
}

function clearParseResult() {
  if (!initialized.value) return
  profile.value.profilePreferenceJson = ''
  parsedPreference.value = null
  parseInterpretation.value = ''
}

async function loadProfile() {
  loading.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    const data = await request.get(`/api/teachers/${teacherId}/profile`)
    if (data) {
      profile.value = {
        availabilityMatrix: parseMatrix(data.availabilityMatrixJson),
        profileNote: data.profileNote || data.specialNote || data.workloadRequirement || '',
        profilePreferenceJson: data.profilePreferenceJson || '',
      }
      parsedPreference.value = parsePreferenceJson(data.profilePreferenceJson)
      parseInterpretation.value = parsedPreference.value?.summary || ''
    }
    initialized.value = true
  } finally {
    loading.value = false
  }
}

async function parseProfile() {
  if (!profile.value.profileNote?.trim()) {
    ElMessage.warning('先写一点其他说明，再让 LLM 解析')
    return
  }
  parsing.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    const data = await request.post(`/api/teachers/${teacherId}/profile/parse`, {
      availabilityMatrixJson: JSON.stringify(normalizeMatrix(profile.value.availabilityMatrix)),
      profileNote: profile.value.profileNote,
    })
    profile.value.profilePreferenceJson = data.profilePreferenceJson
    parsedPreference.value = data.parsedPreference
    parseInterpretation.value = data.interpretation || data.parsedPreference?.summary || '解析完成'
    ElMessage.success('LLM 解析完成，确认无误后可以保存')
  } finally {
    parsing.value = false
  }
}

async function saveProfile() {
  if (profile.value.profileNote?.trim() && !profile.value.profilePreferenceJson) {
    ElMessage.warning('请先通过 LLM 解析并确认其他说明')
    return
  }
  saving.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    await request.put(`/api/teachers/${teacherId}/profile`, {
      availabilityMatrixJson: JSON.stringify(normalizeMatrix(profile.value.availabilityMatrix)),
      profileNote: profile.value.profileNote,
      profilePreferenceJson: profile.value.profilePreferenceJson,
    })
    ElMessage.success('保存成功，已自动更新向量索引')
  } finally {
    saving.value = false
  }
}

watch(
  () => profile.value.profileNote,
  () => clearParseResult(),
)

onMounted(loadProfile)
</script>

<template>
  <div>
    <h2>个人信息 / 教师画像</h2>
    <el-card style="margin-top: 16px; max-width: 920px" v-loading="loading">
      <el-form :model="profile" label-width="120px">
        <el-form-item label="固定周矩阵">
          <div class="availability-panel">
            <div class="availability-help">
              点击格子切换：<el-tag size="small" type="success">可用</el-tag>
              <el-tag size="small" type="info">随意</el-tag>
              <el-tag size="small" type="danger">不可用</el-tag>
              <span>；行是节次，列是星期，保存为 5×7 矩阵。</span>
            </div>
            <table class="availability-table">
              <thead>
                <tr>
                  <th>节次</th>
                  <th v-for="weekday in weekdays" :key="weekday">{{ weekday }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(period, periodIndex) in periods" :key="period">
                  <th>{{ period }}</th>
                  <td v-for="(weekday, weekdayIndex) in weekdays" :key="weekday">
                    <button
                      type="button"
                      :class="cellClass(profile.availabilityMatrix[periodIndex][weekdayIndex])"
                      @click="toggleCell(periodIndex, weekdayIndex)"
                    >
                      {{ cellText(profile.availabilityMatrix[periodIndex][weekdayIndex]) }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-form-item>
        <el-form-item label="其他说明">
          <div class="profile-note-panel">
            <el-input
              v-model="profile.profileNote"
              type="textarea"
              :rows="5"
              placeholder="例如：本学期科研任务较多，希望每周不要超过 10 节；尽量把课集中在周一到周三；理论课上午可以，实验课尽量下午。"
            />
            <div class="profile-actions">
              <el-button type="primary" plain :loading="parsing" @click="parseProfile">提交 LLM 解析</el-button>
              <span class="profile-tip">说明有内容时，必须先解析确认，才允许保存。</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="parsedPreference" label="解析结果">
          <div class="parse-result">
            <el-alert :title="parseInterpretation" type="success" show-icon :closable="false" />
            <pre>{{ JSON.stringify(parsedPreference, null, 2) }}</pre>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="saving" :disabled="!!profile.profileNote?.trim() && !profile.profilePreferenceJson" @click="saveProfile">
            确认并保存
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.availability-panel,
.profile-note-panel,
.parse-result {
  width: 100%;
}

.availability-help,
.profile-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  color: #606266;
  font-size: 13px;
}

.profile-actions {
  margin-top: 10px;
  margin-bottom: 0;
}

.profile-tip {
  color: #909399;
}

.availability-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.availability-table th,
.availability-table td {
  border: 1px solid #dcdfe6;
  padding: 8px;
  text-align: center;
}

.availability-table th {
  background: #f5f7fa;
  color: #606266;
  font-weight: 600;
}

.availability-cell {
  width: 100%;
  min-height: 34px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #f4f4f5;
  color: #606266;
  cursor: pointer;
}

.availability-cell.available {
  border-color: #95d475;
  background: #f0f9eb;
  color: #529b2e;
}

.availability-cell.unavailable {
  border-color: #fab6b6;
  background: #fef0f0;
  color: #c45656;
}

.parse-result pre {
  max-height: 260px;
  overflow: auto;
  margin: 10px 0 0;
  padding: 12px;
  border-radius: 6px;
  background: #f5f7fa;
  color: #303133;
  font-size: 12px;
  line-height: 1.5;
}
</style>
