<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const requests = ref([])
const loading = ref(false)
const statusFilter = ref('')

const detailVisible = ref(false)
const detail = ref(null)

const generating = ref(false)
const topK = ref(5)

const reviewVisible = ref(false)
const reviewForm = ref({ requestId: null, candidateIndex: 1, reviewNote: '' })

async function loadRequests() {
  loading.value = true
  try {
    const qs = statusFilter.value ? `?status=${statusFilter.value}` : ''
    requests.value = await request.get(`/api/adjustment-requests${qs}`)
  } finally {
    loading.value = false
  }
}

async function viewDetail(row) {
  detail.value = await request.get(`/api/adjustment-requests/${row.id}`)
  detailVisible.value = true
}

async function generateSuggestions(row) {
  generating.value = true
  try {
    const data = await request.post(`/api/adjustment-requests/${row.id}/suggestions?topK=${topK.value}`)
    ElMessage.success('生成候选成功')
    detail.value = await request.get(`/api/adjustment-requests/${row.id}`)
    detailVisible.value = true
  } finally {
    generating.value = false
  }
}

function openReview(row) {
  reviewForm.value = { requestId: row.id, candidateIndex: 1, reviewNote: '' }
  reviewVisible.value = true
}

async function confirmAdjustment() {
  await request.post(`/api/adjustment-requests/${reviewForm.value.requestId}/confirm`, {
    candidateIndex: reviewForm.value.candidateIndex,
    reviewNote: reviewForm.value.reviewNote,
  })
  ElMessage.success('调课已确认')
  reviewVisible.value = false
  loadRequests()
}

async function rejectAdjustment(row) {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝调课', { inputPlaceholder: '拒绝原因' })
  await request.post(`/api/adjustment-requests/${row.id}/reject`, { reviewNote: value })
  ElMessage.success('已拒绝')
  loadRequests()
}

function parseAiSuggestion(row) {
  if (!row.aiSuggestion) return null
  try {
    return JSON.parse(row.aiSuggestion)
  } catch {
    return null
  }
}

onMounted(loadRequests)
</script>

<template>
  <div>
    <h2>调课处理</h2>
    <el-card style="margin: 16px 0">
      <el-form inline>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部">
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="已通过" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item label="TopK">
          <el-input-number v-model="topK" :min="1" :max="20" size="small" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRequests">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="requests" border size="small" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="teacherId" label="教师ID" width="80" />
      <el-table-column prop="assignmentId" label="课表ID" width="80" />
      <el-table-column prop="reason" label="调课原因" show-overflow-tooltip />
      <el-table-column prop="preferredTimeText" label="时间偏好" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="AI候选" width="90">
        <template #default="{ row }">
          <el-tag v-if="parseAiSuggestion(row)" type="success" size="small">已生成</el-tag>
          <el-tag v-else type="info" size="small">未生成</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button type="info" size="small" @click="viewDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'SUBMITTED'" type="primary" size="small" :loading="generating" @click="generateSuggestions(row)">生成建议</el-button>
          <el-button v-if="row.status === 'SUBMITTED' && parseAiSuggestion(row)" type="success" size="small" @click="openReview(row)">确认</el-button>
          <el-button v-if="row.status === 'SUBMITTED'" type="danger" size="small" @click="rejectAdjustment(row)">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="调课申请详情" width="700px">
      <div v-if="detail">
        <p><strong>ID：</strong>{{ detail.id }}</p>
        <p><strong>教师ID：</strong>{{ detail.teacherId }}</p>
        <p><strong>课表ID：</strong>{{ detail.assignmentId }}</p>
        <p><strong>原因：</strong>{{ detail.reason }}</p>
        <p><strong>偏好：</strong>{{ detail.preferredTimeText }}</p>
        <p><strong>状态：</strong>{{ detail.status }}</p>
        <p><strong>审核意见：</strong>{{ detail.reviewNote || '无' }}</p>
        <div v-if="parseAiSuggestion(detail)">
          <el-divider />
          <h4>AI 候选方案</h4>
          <el-table :data="parseAiSuggestion(detail).candidates || []" border size="small">
            <el-table-column prop="candidateIndex" label="序号" width="60" />
            <el-table-column prop="summary" label="摘要" />
            <el-table-column prop="newTimeSlotId" label="新时间段ID" width="100" />
            <el-table-column prop="newClassroomId" label="新教室ID" width="100" />
            <el-table-column prop="valid" label="有效" width="70">
              <template #default="{ row }">
                <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{ row.valid ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="conflictMessage" label="冲突信息" show-overflow-tooltip />
          </el-table>
        </div>
      </div>
    </el-dialog>

    <!-- Review Dialog -->
    <el-dialog v-model="reviewVisible" title="确认调课" width="480px">
      <el-form :model="reviewForm" label-width="100px">
        <el-form-item label="候选序号">
          <el-input-number v-model="reviewForm.candidateIndex" :min="1" />
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input v-model="reviewForm.reviewNote" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAdjustment">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
