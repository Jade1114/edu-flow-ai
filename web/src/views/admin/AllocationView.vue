<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const tasks = ref([])
const taskDialog = ref(false)
const taskForm = ref({ id: null, name: '', description: '', priorityRule: '优先匹配课程能力' })

const schemes = ref([])
const schemeVisible = ref(false)
const currentTaskId = ref(null)

const generating = ref(false)
const topK = ref(5)

async function loadTasks() {
  tasks.value = await request.get('/api/allocation-tasks')
}

function openTaskDialog(row) {
  taskForm.value = row
    ? { id: row.id, name: row.name, description: row.description || '', priorityRule: row.priorityRule || '' }
    : { id: null, name: '', description: '', priorityRule: '优先匹配课程能力' }
  taskDialog.value = true
}

async function saveTask() {
  if (!taskForm.value.name) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (taskForm.value.id) {
    await request.put(`/api/allocation-tasks/${taskForm.value.id}`, taskForm.value)
  } else {
    await request.post('/api/allocation-tasks', taskForm.value)
  }
  ElMessage.success('保存成功')
  taskDialog.value = false
  loadTasks()
}

async function viewSchemes(taskId) {
  currentTaskId.value = taskId
  schemes.value = await request.get(`/api/allocation-tasks/${taskId}/schemes`)
  schemeVisible.value = true
}

async function generateSchemes(taskId) {
  generating.value = true
  try {
    const data = await request.post(`/api/allocation-tasks/${taskId}/schemes?topK=${topK.value}`)
    ElMessage.success(`生成成功，共 ${data.schemeCount || 0} 个候选方案`)
    viewSchemes(taskId)
  } finally {
    generating.value = false
  }
}

async function confirmScheme(schemeId) {
  await ElMessageBox.confirm('确认将此方案设为正式课表？', '提示', { type: 'warning' })
  await request.post(`/api/allocation-schemes/${schemeId}/confirm`)
  ElMessage.success('确认成功')
  viewSchemes(currentTaskId.value)
  loadTasks()
}

async function viewSchemeDetail(schemeId) {
  const detail = await request.get(`/api/allocation-schemes/${schemeId}`)
  schemeDetail.value = detail
  detailVisible.value = true
}

const detailVisible = ref(false)
const schemeDetail = ref(null)

onMounted(loadTasks)
</script>

<template>
  <div>
    <h2>分课任务管理</h2>
    <div style="margin: 16px 0; display: flex; gap: 12px; align-items: center">
      <el-button type="primary" @click="openTaskDialog()">新建任务</el-button>
      <span style="color: #909399; font-size: 13px">TopK：</span>
      <el-input-number v-model="topK" :min="1" :max="20" size="small" style="width: 100px" />
    </div>

    <el-table :data="tasks" border size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="任务名称" />
      <el-table-column prop="priorityRule" label="优先规则" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="createdBy" label="创建人" width="100" />
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openTaskDialog(row)">编辑</el-button>
          <el-button type="success" size="small" :loading="generating" @click="generateSchemes(row.id)">生成方案</el-button>
          <el-button type="info" size="small" @click="viewSchemes(row.id)">查看方案</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Task Dialog -->
    <el-dialog v-model="taskDialog" :title="taskForm.id ? '编辑任务' : '新建任务'" width="520px">
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="taskForm.name" />
        </el-form-item>
        <el-form-item label="优先规则">
          <el-input v-model="taskForm.priorityRule" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTask">保存</el-button>
      </template>
    </el-dialog>

    <!-- Schemes Dialog -->
    <el-dialog v-model="schemeVisible" title="候选方案" width="800px">
      <el-table :data="schemes" border size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="schemeName" label="方案名称" />
        <el-table-column prop="score" label="分数" width="70" />
        <el-table-column prop="valid" label="有效" width="70">
          <template #default="{ row }">
            <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{ row.valid ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="conflictSummary" label="冲突摘要" show-overflow-tooltip />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewSchemeDetail(row.id)">详情</el-button>
            <el-button type="success" size="small" :disabled="!row.valid || row.status !== 'CANDIDATE'" @click="confirmScheme(row.id)">确认</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- Scheme Detail Dialog -->
    <el-dialog v-model="detailVisible" title="方案详情" width="900px">
      <div v-if="schemeDetail">
        <p><strong>方案名称：</strong>{{ schemeDetail.schemeName }}</p>
        <p><strong>摘要：</strong>{{ schemeDetail.summary }}</p>
        <p><strong>满足情况：</strong>{{ schemeDetail.satisfiedSummary }}</p>
        <p><strong>冲突摘要：</strong>{{ schemeDetail.conflictSummary || '无' }}</p>
        <el-divider />
        <el-table :data="schemeDetail.items || []" border size="small">
          <el-table-column prop="courseName" label="课程" />
          <el-table-column prop="classGroupName" label="班级" />
          <el-table-column prop="teacherName" label="教师" />
          <el-table-column prop="classroomName" label="教室" />
          <el-table-column prop="timeSlotLabel" label="时间段" />
          <el-table-column prop="valid" label="有效" width="70">
            <template #default="{ row }">
              <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{ row.valid ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="conflictMessage" label="冲突信息" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>
