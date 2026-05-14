<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const requests = ref([])
const loading = ref(false)
const statusFilter = ref('PENDING')

async function loadRequests() {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value) params.status = statusFilter.value
    const qs = new URLSearchParams(params).toString()
    requests.value = await request.get(`/api/adjustment-requests${qs ? '?' + qs : ''}`)
  } finally {
    loading.value = false
  }
}

function statusTag(status) {
  const map = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger' }
  return map[status] || 'info'
}

// === 课程表视图（处理调课）===
const timetableVisible = ref(false)
const currentReq = ref(null)
const assignments = ref([])
const allTimeSlots = ref([])
const currentWeek = ref(1)
const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
let timeSlotMap = {}

async function openTimetable(row) {
  currentReq.value = await request.get(`/api/adjustment-requests/${row.id}`)
  // 加载全局课表（所有教师的）+ 时间段列表
  const [items, slots] = await Promise.all([
    request.get('/api/course-assignments'),
    request.get('/api/time-slots'),
  ])
  assignments.value = items
  allTimeSlots.value = slots
  buildTimeSlotMap(slots)
  if (items.length > 0) {
    const minWeek = Math.min(...items.map(a => a.weekNumber))
    if (minWeek > 0) currentWeek.value = minWeek
  }
  pendingMove.value = null
  timetableVisible.value = true
}

function buildTimeSlotMap(slots) {
  timeSlotMap = {}
  for (const ts of slots) {
    timeSlotMap[`${ts.weekNumber}-${ts.dayOfWeek}-${ts.periodIndex}`] = ts.id
  }
}

const weekItems = computed(() => {
  return assignments.value.filter(a => a.weekNumber === currentWeek.value)
})

// itemsAtSlot 包含待移动项的预览
function itemsAtSlot(dayOfWeek, periodIndex) {
  const base = weekItems.value.filter(
    item => item.dayOfWeek === dayOfWeek && item.periodIndex === periodIndex
  )
  // 如果有待移动项，从原位置移除、在新位置加入
  if (pendingMove.value) {
    const filtered = base.filter(item => item.id !== pendingMove.value.itemId)
    if (pendingMove.value.dayOfWeek === dayOfWeek && pendingMove.value.periodIndex === periodIndex
        && pendingMove.value.weekNumber === currentWeek.value) {
      // 找到原 item 对象
      const original = weekItems.value.find(i => i.id === pendingMove.value.itemId)
      if (original) {
        filtered.push({ ...original, dayOfWeek, periodIndex, timeSlotId: pendingMove.value.targetTimeSlotId })
      }
    }
    return filtered
  }
  return base
}

function isAdjustTarget(item) {
  return currentReq.value && item.id === currentReq.value.assignmentId
}

function isMovedItem(item) {
  return pendingMove.value && item.id === pendingMove.value.itemId
}

function allWeeks() {
  const weeks = [...new Set(assignments.value.map(a => a.weekNumber))]
  return weeks.sort((a, b) => a - b)
}

function goToWeek(week) {
  if (week >= 1 && week <= 18) currentWeek.value = week
}

// === 拖拽 + 暂存移动 ===
const dragItem = ref(null)
const dropTarget = ref(null)
const pendingMove = ref(null) // { itemId, targetTimeSlotId, dayOfWeek, periodIndex, weekNumber }
const savingMove = ref(false)

function onDragStart(e, item) {
  dragItem.value = item
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(item.id))
}

function onDragOver(e, day, period) {
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  dropTarget.value = `${day}-${period}`
}

function onDragLeave() {
  dropTarget.value = null
}

function onDrop(e, day, period) {
  e.preventDefault()
  dropTarget.value = null
  const item = dragItem.value
  if (!item) return

  if (!isAdjustTarget(item)) {
    ElMessage.warning('只能拖动标黄的调课片段')
    dragItem.value = null
    return
  }

  const key = `${currentWeek.value}-${day}-${period}`
  const targetTimeSlotId = timeSlotMap[key]
  if (!targetTimeSlotId) {
    ElMessage.warning('该时间段不存在')
    dragItem.value = null
    return
  }
  if (targetTimeSlotId === item.timeSlotId && currentWeek.value === item.weekNumber
      && day === item.dayOfWeek && period === item.periodIndex) {
    dragItem.value = null
    return  // 没变
  }

  // 暂存移动，不直接保存
  pendingMove.value = {
    itemId: item.id,
    targetTimeSlotId,
    dayOfWeek: day,
    periodIndex: period,
    weekNumber: currentWeek.value,
  }
  dragItem.value = null
}

async function saveMove() {
  if (!pendingMove.value) return
  savingMove.value = true
  try {
      const original = assignments.value.find(i => i.id === pendingMove.value.itemId)
      await request.put(`/api/course-assignments/${pendingMove.value.itemId}/move`, null, {
        params: { timeSlotId: pendingMove.value.targetTimeSlotId, classroomId: original?.classroomId }
      })
    // 标记调课申请为 APPROVED
    await request.post(`/api/adjustment-requests/${currentReq.value.id}/confirm`, {
      candidateIndex: 0,
      reviewNote: '已通过拖拽调整'
    })
    ElMessage.success('调课成功')
    pendingMove.value = null
    // 刷新全局课表 + 申请列表
    const [items] = await Promise.all([
      request.get('/api/course-assignments'),
      loadRequests(),
    ])
    assignments.value = items
  } catch (e) {
    // 错误由 axios 拦截器统一提示
  } finally {
    savingMove.value = false
  }
}

function cancelMove() {
  pendingMove.value = null
}

// === 拒绝申请 ===
async function rejectRequest(row) {
  await ElMessageBox.confirm('确认拒绝该调课申请？', '提示', { type: 'warning' })
  try {
    await request.post(`/api/adjustment-requests/${row.id}/reject`, { reviewNote: '教务拒绝' })
    ElMessage.success('已拒绝')
    loadRequests()
    if (timetableVisible.value && currentReq.value?.id === row.id) {
      timetableVisible.value = false
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

onMounted(loadRequests)
</script>

<template>
  <div>
    <h2>调课处理</h2>
    <div style="margin: 16px 0; display: flex; gap: 12px; align-items: center">
      <el-radio-group v-model="statusFilter" @change="loadRequests" size="small">
        <el-radio-button value="PENDING">待处理</el-radio-button>
        <el-radio-button value="APPROVED">已通过</el-radio-button>
        <el-radio-button value="REJECTED">已拒绝</el-radio-button>
        <el-radio-button value="">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="requests" border size="small" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="reason" label="调课原因" show-overflow-tooltip />
      <el-table-column prop="preferredTimeText" label="调课倾向" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="申请时间" width="170" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openTimetable(row)" v-if="row.status === 'PENDING'">调课</el-button>
          <el-button type="danger" size="small" @click="rejectRequest(row)" v-if="row.status === 'PENDING'">拒绝</el-button>
          <span v-else style="color: #909399; font-size: 13px">—</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 调课处理 - 课程表视图 -->
    <el-dialog v-model="timetableVisible" title="调课处理" width="960px" top="2vh">
      <template v-if="currentReq">
        <div style="margin-bottom: 12px; padding: 12px; background: var(--el-color-warning-light-9, #fdf6ec); border-radius: 6px">
          <p><strong>调课原因：</strong>{{ currentReq.reason }}</p>
          <p v-if="currentReq.preferredTimeText"><strong>调课倾向：</strong>{{ currentReq.preferredTimeText }}</p>
          <p style="color: #e6a23c; font-size: 13px">💡 拖拽标黄的课程块到目标位置，点击「保存调整」完成调课</p>
        </div>

        <!-- 周次导航 -->
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
          <el-button :disabled="currentWeek <= 1" size="small" @click="goToWeek(currentWeek - 1)">‹ 上一周</el-button>
          <el-select v-model="currentWeek" size="small" style="width: 110px">
            <el-option v-for="w in allWeeks()" :key="w" :label="`第 ${w} 周`" :value="w" />
          </el-select>
          <el-button :disabled="currentWeek >= 18" size="small" @click="goToWeek(currentWeek + 1)">下一周 ›</el-button>
          <span style="color: #909399; font-size: 13px">（全局课表，第 {{ currentWeek }} 周）</span>
        </div>

        <!-- 操作栏 -->
        <div v-if="pendingMove" style="margin-bottom: 8px; display: flex; gap: 8px; align-items: center">
          <el-tag type="warning">已移动到新位置，预览中</el-tag>
          <el-button type="primary" size="small" :loading="savingMove" @click="saveMove">保存调整</el-button>
          <el-button size="small" @click="cancelMove">取消</el-button>
        </div>

        <!-- 课程表网格 -->
        <div style="overflow-x: auto">
          <table class="timetable" style="width: 100%; border-collapse: collapse; font-size: 13px">
            <thead>
              <tr>
                <th class="timetable-th" style="width: 60px">节次</th>
                <th v-for="day in dayNames" :key="day" class="timetable-th" style="min-width: 120px">{{ day }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="period in 5" :key="period">
                <td class="timetable-label">第{{ period }}节</td>
                <td v-for="day in 7" :key="day" class="timetable-cell"
                  :class="{
                    'slot-hover': itemsAtSlot(day, period).length > 0 || pendingMove,
                    'drop-target': dropTarget === `${day}-${period}`
                  }"
                  @dragover="onDragOver($event, day, period)"
                  @dragleave="onDragLeave"
                  @drop="onDrop($event, day, period)">
                  <div v-if="itemsAtSlot(day, period).length > 0" style="display: flex; flex-direction: column; gap: 3px">
                    <div v-for="item in itemsAtSlot(day, period)" :key="item.id" draggable="true"
                      @dragstart="onDragStart($event, item)"
                      :style="{
                        padding: '3px 5px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        lineHeight: '1.4',
                        cursor: isAdjustTarget(item) ? 'grab' : 'default',
                        background: isMovedItem(item) ? 'var(--el-color-success, #67c23a)'
                          : isAdjustTarget(item) ? 'var(--el-color-warning, #e6a23c)'
                          : 'var(--el-color-primary-light-9, #ecf5ff)',
                        color: isAdjustTarget(item) || isMovedItem(item) ? '#fff' : 'var(--el-color-primary, #409eff)',
                        opacity: isMovedItem(item) ? 0.85 : 1,
                      }">
                      <div style="font-weight: 600">{{ item.courseName }}</div>
                      <div>{{ item.classroomName }} · {{ item.teacherName }}</div>
                      <div style="font-size: 11px; opacity: 0.8">{{ item.classGroupName }}</div>
                      <div v-if="isMovedItem(item)" style="font-size: 11px; margin-top: 2px">⬅ 新位置</div>
                    </div>
                  </div>
                  <div v-else style="color: #ccc; text-align: center; font-size: 11px; line-height: 40px">空</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <template #footer>
        <el-button @click="timetableVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.slot-hover { transition: background 0.15s; }
.slot-hover:hover { background: var(--el-color-primary-light-9, #ecf5ff); }
.drop-target { background: var(--el-color-success-light-9, #f0f9eb) !important; }
.timetable td, .timetable th { border-color: var(--el-border-color-light, #dcdfe6); }
.timetable-th {
  padding: 8px 4px; border: 1px solid var(--border, #dcdfe6);
  background: var(--el-fill-color-light, #f5f7fa); text-align: center;
}
.timetable-label {
  padding: 8px 4px; border: 1px solid var(--border, #dcdfe6);
  text-align: center; font-weight: bold; background: var(--el-fill-color-light, #f5f7fa);
}
.timetable-cell {
  padding: 4px; border: 1px solid var(--border, #dcdfe6);
  vertical-align: top; min-height: 60px; height: auto;
}
</style>
