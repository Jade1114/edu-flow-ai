<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'

const assignments = ref([])
const loading = ref(false)
const filters = ref({ teacherId: '', classGroupId: '', courseId: '', weekNumber: '', dayOfWeek: '' })

async function loadAssignments() {
  loading.value = true
  try {
    const params = {}
    Object.entries(filters.value).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) params[k] = v
    })
    const qs = new URLSearchParams(params).toString()
    assignments.value = await request.get(`/api/course-assignments${qs ? '?' + qs : ''}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadAssignments)
</script>

<template>
  <div>
    <h2>正式课表查询</h2>
    <el-card style="margin: 16px 0">
      <el-form :model="filters" inline>
        <el-form-item label="教师ID">
          <el-input v-model="filters.teacherId" placeholder="教师ID" clearable />
        </el-form-item>
        <el-form-item label="班级ID">
          <el-input v-model="filters.classGroupId" placeholder="班级ID" clearable />
        </el-form-item>
        <el-form-item label="课程ID">
          <el-input v-model="filters.courseId" placeholder="课程ID" clearable />
        </el-form-item>
        <el-form-item label="周次">
          <el-input v-model="filters.weekNumber" placeholder="周次" clearable />
        </el-form-item>
        <el-form-item label="星期">
          <el-input v-model="filters.dayOfWeek" placeholder="1-7" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadAssignments">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="assignments" border size="small" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="courseName" label="课程" />
      <el-table-column prop="classGroupName" label="班级" />
      <el-table-column prop="teacherName" label="教师" />
      <el-table-column prop="classroomName" label="教室" />
      <el-table-column prop="timeSlotLabel" label="时间段" />
      <el-table-column prop="weekNumber" label="周次" width="70" />
      <el-table-column prop="dayOfWeek" label="星期" width="70" />
      <el-table-column prop="periodIndex" label="节次" width="70" />
      <el-table-column prop="status" label="状态" width="90" />
    </el-table>
  </div>
</template>
