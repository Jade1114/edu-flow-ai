<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const assignments = ref([])
const loading = ref(false)
const filters = ref({ weekNumber: '', dayOfWeek: '' })
const viewMode = ref('table')
const currentWeek = ref(1)
const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

async function loadTimetable() {
  loading.value = true
  try {
    const teacherId = auth.user?.teacherId || auth.user?.id
    const params = {}
    if (filters.value.weekNumber) params.weekNumber = filters.value.weekNumber
    if (filters.value.dayOfWeek) params.dayOfWeek = filters.value.dayOfWeek
    const qs = new URLSearchParams(params).toString()
    assignments.value = await request.get(`/api/teachers/${teacherId}/course-assignments${qs ? '?' + qs : ''}`)
    if (assignments.value.length > 0) {
      const minWeek = Math.min(...assignments.value.map(a => a.weekNumber))
      if (minWeek > 0) currentWeek.value = minWeek
    }
  } finally {
    loading.value = false
  }
}

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

// === 调课申请 ===
const adjustDialog = ref(false)
const adjustItem = ref(null)
const adjustForm = ref({ reason: '', preferredTimeText: '' })
const submitting = ref(false)

function openAdjustDialog(item) {
  adjustItem.value = item
  adjustForm.value = { reason: '', preferredTimeText: '' }
  adjustDialog.value = true
}

async function submitAdjust() {
  if (!adjustForm.value.reason) {
    ElMessage.warning('请填写调课原因')
    return
  }
  submitting.value = true
  try {
    await request.post('/api/adjustment-requests', {
      assignmentId: adjustItem.value.id,
      reason: adjustForm.value.reason,
      preferredTimeText: adjustForm.value.preferredTimeText || null,
    })
    ElMessage.success('调课申请已提交')
    adjustDialog.value = false
  } catch (e) {
    ElMessage.error('提交失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
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
      <el-table-column prop="courseName" label="课程" />
      <el-table-column prop="classGroupName" label="班级" />
      <el-table-column prop="classroomName" label="教室" />
      <el-table-column prop="timeSlotLabel" label="时间段" />
      <el-table-column prop="weekNumber" label="周次" width="70" />
      <el-table-column prop="dayOfWeek" label="星期" width="70" />
      <el-table-column prop="periodIndex" label="节次" width="70" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button type="warning" size="small" @click="openAdjustDialog(row)">调课</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 课程表视图 -->
    <div v-if="viewMode === 'timetable'" v-loading="loading">
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
                    style="padding: 3px 5px; border-radius: 4px; font-size: 12px; line-height: 1.4; background: var(--el-color-primary-light-9, #ecf5ff); color: var(--el-color-primary, #409eff); cursor: pointer"
                    @click="openAdjustDialog(item)">
                    <div style="font-weight: 600">{{ item.courseName }}</div>
                    <div style="color: #666">{{ item.classroomName }} · {{ item.teacherName }}</div>
                    <div style="color: #999; font-size: 11px">{{ item.classGroupName }}</div>
                    <div style="font-size: 11px; color: #409eff; margin-top: 2px">申请调课</div>
                  </div>
                </div>
                <div v-else style="color: #ccc; text-align: center; font-size: 11px; line-height: 40px">空</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 调课申请弹窗 -->
    <el-dialog v-model="adjustDialog" title="申请调课" width="500px">
      <p v-if="adjustItem" style="margin-bottom: 12px; color: #666">
        <strong>{{ adjustItem.courseName }}</strong> ·
        {{ adjustItem.classroomName }} ·
        第{{ adjustItem.weekNumber }}周 ·
        {{ adjustItem.timeSlotLabel }}
      </p>
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="调课原因" required>
          <el-input v-model="adjustForm.reason" type="textarea" :rows="3" placeholder="请说明调课原因" />
        </el-form-item>
        <el-form-item label="调课倾向">
          <el-input v-model="adjustForm.preferredTimeText" type="textarea" :rows="2" placeholder="可选，例如：希望调整到周三或周四上午" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAdjust">提交申请</el-button>
      </template>
    </el-dialog>
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
