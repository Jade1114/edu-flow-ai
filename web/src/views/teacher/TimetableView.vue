<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { useAuthStore } from '@/stores/auth.js'

const auth = useAuthStore()
const assignments = ref([])
const loading = ref(false)
const filters = ref({ weekNumber: '', dayOfWeek: '' })

async function loadTimetable() {
  loading.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    const params = {}
    if (filters.value.weekNumber) params.weekNumber = filters.value.weekNumber
    if (filters.value.dayOfWeek) params.dayOfWeek = filters.value.dayOfWeek
    const qs = new URLSearchParams(params).toString()
    assignments.value = await request.get(`/api/teachers/${teacherId}/course-assignments${qs ? '?' + qs : ''}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadTimetable)
</script>

<template>
  <div>
    <h2>我的课表</h2>
    <el-card style="margin: 16px 0">
      <el-form :model="filters" inline>
        <el-form-item label="周次">
          <el-input v-model="filters.weekNumber" placeholder="周次" clearable />
        </el-form-item>
        <el-form-item label="星期">
          <el-input v-model="filters.dayOfWeek" placeholder="1-7" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTimetable">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="assignments" border size="small" v-loading="loading">
      <el-table-column prop="courseName" label="课程" />
      <el-table-column prop="classGroupName" label="班级" />
      <el-table-column prop="classroomName" label="教室" />
      <el-table-column prop="timeSlotLabel" label="时间段" />
      <el-table-column prop="weekNumber" label="周次" width="70" />
      <el-table-column prop="dayOfWeek" label="星期" width="70" />
      <el-table-column prop="periodIndex" label="节次" width="70" />
    </el-table>
  </div>
</template>
