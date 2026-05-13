<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const profile = ref({
  availableTimeText: '',
  unavailableTimeText: '',
  workloadRequirement: '',
  specialNote: '',
})
const loading = ref(false)
const saving = ref(false)

async function loadProfile() {
  loading.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    const data = await request.get(`/api/teachers/${teacherId}/profile`)
    if (data) {
      profile.value = {
        availableTimeText: data.availableTimeText || '',
        unavailableTimeText: data.unavailableTimeText || '',
        workloadRequirement: data.workloadRequirement || '',
        specialNote: data.specialNote || '',
      }
    }
  } catch {
    // 可能还没有profile，保持默认值
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    await request.put(`/api/teachers/${teacherId}/profile`, profile.value)
    ElMessage.success('保存成功，已自动更新向量索引')
  } finally {
    saving.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div>
    <h2>个人信息 / 教师画像</h2>
    <el-card style="margin-top: 16px; max-width: 720px" v-loading="loading">
      <el-form :model="profile" label-width="120px">
        <el-form-item label="可用时间">
          <el-input v-model="profile.availableTimeText" type="textarea" :rows="3" placeholder="例如：周一上午、周三下午、周五上午" />
        </el-form-item>
        <el-form-item label="不可用时间">
          <el-input v-model="profile.unavailableTimeText" type="textarea" :rows="2" placeholder="例如：周二全天、周五下午" />
        </el-form-item>
        <el-form-item label="课时要求">
          <el-input v-model="profile.workloadRequirement" type="textarea" :rows="2" placeholder="例如：本学期希望每周课程不要超过 8 学时" />
        </el-form-item>
        <el-form-item label="特殊说明">
          <el-input v-model="profile.specialNote" type="textarea" :rows="3" placeholder="例如：本学期承担科研任务" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
