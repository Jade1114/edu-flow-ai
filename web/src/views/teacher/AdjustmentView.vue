<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const assignments = ref([])
const requests = ref([])
const loading = ref(false)

const dialogVisible = ref(false)
const form = ref({ assignmentId: null, reason: '', preferredTimeText: '' })
const formRef = ref()
const rules = {
  assignmentId: [{ required: true, message: '请选择课程', trigger: 'change' }],
  reason: [{ required: true, message: '请输入调课原因', trigger: 'blur' }],
}

async function loadAssignments() {
  const teacherId = auth.user?.teacherId || auth.user?.id
  assignments.value = await request.get(`/api/teachers/${teacherId}/course-assignments`)
}

async function loadRequests() {
  loading.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    requests.value = await request.get(`/api/adjustment-requests?teacherId=${teacherId}`)
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.value = { assignmentId: null, reason: '', preferredTimeText: '' }
  dialogVisible.value = true
}

async function submitRequest() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  await request.post('/api/adjustment-requests', {
    assignmentId: form.value.assignmentId,
    teacherId: auth.user?.teacherId || auth.user?.id,
    reason: form.value.reason,
    preferredTimeText: form.value.preferredTimeText,
  })
  ElMessage.success('提交成功')
  dialogVisible.value = false
  loadRequests()
}

onMounted(() => {
  loadAssignments()
  loadRequests()
})
</script>

<template>
  <div>
    <h2>调课申请</h2>
    <div style="margin: 16px 0">
      <el-button type="primary" @click="openDialog">提交调课申请</el-button>
    </div>

    <h3 style="margin-top: 24px; font-size: 16px">我的调课记录</h3>
    <el-table :data="requests" border size="small" v-loading="loading" style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="assignmentId" label="课表ID" width="80" />
      <el-table-column prop="reason" label="调课原因" show-overflow-tooltip />
      <el-table-column prop="preferredTimeText" label="时间偏好" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="reviewNote" label="审核意见" show-overflow-tooltip />
    </el-table>

    <!-- Submit Dialog -->
    <el-dialog v-model="dialogVisible" title="提交调课申请" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="选择课程" prop="assignmentId">
          <el-select v-model="form.assignmentId" placeholder="请选择要调整的课程" style="width: 100%">
            <el-option
              v-for="a in assignments"
              :key="a.id"
              :label="`${a.courseName} - ${a.timeSlotLabel}`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="调课原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="请说明调课原因" />
        </el-form-item>
        <el-form-item label="时间偏好">
          <el-input v-model="form.preferredTimeText" type="textarea" :rows="2" placeholder="例如：希望调整到周三或周四上午" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRequest">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>
