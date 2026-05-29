<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request'

const assignments = ref([])
const loading = ref(false)
const filters = ref({ teacherId: '', classGroupId: '', courseId: '', weekNumber: '', dayOfWeek: '' })
const viewMode = ref('table')
const currentWeek = ref(1)
const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

async function loadAssignments() {
  loading.value = true
  try {
    const params = {}
    Object.entries(filters.value).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) params[k] = v
    })
    const qs = new URLSearchParams(params).toString()
    assignments.value = await request.get(`/api/course-assignments${qs ? '?' + qs : ''}`)
    if (assignments.value.length > 0) {
      // 默认跳到最早有课的周
      const minWeek = Math.min(...assignments.value.map(a => a.weekNumber))
      if (minWeek > 0) currentWeek.value = minWeek
    }
  } finally {
    loading.value = false
  }
}

// 课程表视图：当前周的排课
const weekItems = computed(() => {
  return assignments.value.filter(a => a.weekNumber === currentWeek.value)
})

function itemsAtSlot(dayOfWeek, periodIndex) {
  return weekItems.value.filter(
    item => item.dayOfWeek === dayOfWeek && item.periodIndex === periodIndex
  )
}

function allWeeks() {
  const weeks = [...new Set(assignments.value.map(a => a.weekNumber))]
  return weeks.sort((a, b) => a - b)
}

function goToWeek(week) {
  if (week >= 1 && week <= 18) currentWeek.value = week
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

    <!-- 视图切换 -->
    <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 12px">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="table">表格视图</el-radio-button>
        <el-radio-button value="timetable">课程表视图</el-radio-button>
      </el-radio-group>
      <span v-if="viewMode === 'timetable'" style="color: #909399; font-size: 13px">
        共 {{ assignments.length }} 条记录
      </span>
    </div>

    <!-- 表格视图 -->
    <el-table v-if="viewMode === 'table'" :data="assignments" border size="small" v-loading="loading">
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

    <!-- 课程表视图 -->
    <div v-if="viewMode === 'timetable'" v-loading="loading">
      <!-- 周次导航 -->
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
        <el-button :disabled="currentWeek <= 1" size="small" @click="goToWeek(currentWeek - 1)">
          ‹ 上一周
        </el-button>
        <el-select v-model="currentWeek" size="small" style="width: 110px" placeholder="选择周次">
          <el-option v-for="w in allWeeks()" :key="w" :label="`第 ${w} 周`" :value="w" />
        </el-select>
        <el-button :disabled="currentWeek >= 18" size="small" @click="goToWeek(currentWeek + 1)">
          下一周 ›
        </el-button>
        <span style="color: #909399; font-size: 13px; margin-left: 8px">
          （第 {{ currentWeek }} 周，{{ weekItems.length }} 个排课片段）
        </span>
      </div>

      <!-- 课程表网格 -->
      <div style="overflow-x: auto">
        <table class="timetable" style="width: 100%; border-collapse: collapse; font-size: 13px">
          <thead>
            <tr>
              <th class="timetable-th" style="width: 70px">节次</th>
              <th v-for="day in dayNames" :key="day" class="timetable-th" style="min-width: 130px">
                {{ day }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="period in 5" :key="period">
              <td class="timetable-label">第{{ period }}节</td>
              <td v-for="day in 7" :key="day" class="timetable-cell"
                :class="{ 'slot-hover': itemsAtSlot(day, period).length > 0 }">
                <div v-if="itemsAtSlot(day, period).length > 0" style="display: flex; flex-direction: column; gap: 3px">
                  <div v-for="item in itemsAtSlot(day, period)" :key="item.id"
                    style="padding: 3px 5px; border-radius: 4px; font-size: 12px; line-height: 1.4; background: var(--el-color-primary-light-9, #ecf5ff); color: var(--el-color-primary, #409eff)">
                    <div style="font-weight: 600">{{ item.courseName }}</div>
                    <div style="color: #666">{{ item.classroomName }} · {{ item.teacherName }}</div>
                    <div style="color: #999; font-size: 11px">{{ item.classGroupName }}</div>
                  </div>
                </div>
                <div v-else style="color: #ccc; text-align: center; font-size: 11px; line-height: 40px">空</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slot-hover {
  transition: background 0.15s;
}
.slot-hover:hover {
  background: var(--el-color-primary-light-9, #ecf5ff);
}
.timetable td, .timetable th {
  border-color: var(--el-border-color-light, #dcdfe6);
}
.timetable-th {
  padding: 8px 4px;
  border: 1px solid var(--border, #dcdfe6);
  background: var(--el-fill-color-light, #f5f7fa);
  text-align: center;
}
.timetable-label {
  padding: 8px 4px;
  border: 1px solid var(--border, #dcdfe6);
  text-align: center;
  font-weight: bold;
  background: var(--el-fill-color-light, #f5f7fa);
}
.timetable-cell {
  padding: 4px;
  border: 1px solid var(--border, #dcdfe6);
  vertical-align: top;
  cursor: pointer;
  min-height: 60px;
  height: auto;
}
</style>
