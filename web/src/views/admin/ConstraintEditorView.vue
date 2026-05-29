<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Switch, Refresh } from '@element-plus/icons-vue'

// ── Task selector ──────────────────────────────────────────────
const tasks = ref([])
const selectedTaskId = ref(null)
const loadingTasks = ref(false)

async function loadTasks() {
  loadingTasks.value = true
  try {
    const data = await request.get('/api/allocation-tasks')
    tasks.value = Array.isArray(data) ? data : []
    if (tasks.value.length > 0 && !selectedTaskId.value) {
      selectedTaskId.value = tasks.value[0].id
      loadConstraints()
    }
  } finally {
    loadingTasks.value = false
  }
}

// ── Constraints ────────────────────────────────────────────────
const constraints = ref([])
const constraintsLoading = ref(false)
const config = ref(null)

async function loadConstraints() {
  if (!selectedTaskId.value) return
  constraintsLoading.value = true
  try {
    const data = await request.get(`/api/allocation-tasks/${selectedTaskId.value}`)
    config.value = data?.generationConfig || null
    const raw = config.value?.llmOverrides
    if (raw) {
      try {
        const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
        constraints.value = parsed?.overrides || []
      } catch {
        constraints.value = []
      }
    } else {
      constraints.value = []
    }
  } finally {
    constraintsLoading.value = false
  }
}

// ── Translation ────────────────────────────────────────────────
const inputText = ref('')
const translating = ref(false)
const previewConstraints = ref([])

async function translateInput() {
  const text = inputText.value.trim()
  if (!text) {
    ElMessage.warning('请输入约束描述')
    return
  }
  translating.value = true
  previewConstraints.value = []
  try {
    const result = await request.post(
      `/api/allocation-tasks/${selectedTaskId.value}/translate-constraint`,
      { text }
    )
    if (result?.success && result?.constraints) {
      previewConstraints.value = result.constraints
    } else if (result?.constraints) {
      previewConstraints.value = result.constraints
    } else {
      ElMessage.error('翻译失败：返回格式异常')
    }
  } catch (e) {
    ElMessage.error('翻译请求失败: ' + (e.message || ''))
  } finally {
    translating.value = false
  }
}

async function applyConstraints() {
  if (!selectedTaskId.value || previewConstraints.value.length === 0) return
  const merged = [...constraints.value, ...previewConstraints.value]
  const payload = { llmOverrides: JSON.stringify({ overrides: merged }) }
  try {
    await request.put(`/api/allocation-tasks/${selectedTaskId.value}`, {
      generationConfig: { ...config.value, ...payload }
    })
    ElMessage.success(`已应用 ${previewConstraints.value.length} 条约束`)
    previewConstraints.value = []
    inputText.value = ''
    await loadConstraints()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || ''))
  }
}

function cancelPreview() {
  previewConstraints.value = []
  inputText.value = ''
}

// ── Toggle / Delete ────────────────────────────────────────────
async function toggleConstraint(constraintId) {
  try {
    await request.put(
      `/api/allocation-tasks/${selectedTaskId.value}/constraints/toggle`,
      { constraintId }
    )
    await loadConstraints()
  } catch (e) {
    ElMessage.error('取消失败: ' + (e.message || ''))
  }
}

async function deleteConstraint(constraintId) {
  try {
    await ElMessageBox.confirm('确定删除此约束？', '确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await request.delete(
      `/api/allocation-tasks/${selectedTaskId.value}/constraints/${constraintId}`
    )
    ElMessage.success('已删除')
    await loadConstraints()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.message || ''))
    }
  }
}

function severityTag(priority) {
  const map = { critical: 'danger', strong: 'warning', normal: 'info', mild: '' }
  return map[priority] || 'info'
}

function severityLabel(priority) {
  const map = { critical: '完全禁止', strong: '强烈偏好', normal: '一般约束', mild: '轻微倾向' }
  return map[priority] || priority
}

function scopeLabel(scope) {
  if (!scope || scope.type === 'all') return '全部任务'
  if (scope.type === 'teacher') return `教师: ${scope.teacher_name || scope.teacher_id || '?'}`
  if (scope.type === 'course') return `课程: ${(scope.course_types || []).join(', ')}`
  if (scope.type === 'student_count') return `人数: ${scope.min || 0}人以上`
  return scope.type
}

onMounted(loadTasks)
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 16px;">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px;">
      <h2 style="margin: 0;">排课约束干预</h2>
      <el-select
        v-model="selectedTaskId"
        placeholder="选择排课任务"
        style="width: 280px;"
        @change="loadConstraints"
        :loading="loadingTasks"
      >
        <el-option
          v-for="t in tasks"
          :key="t.id"
          :label="`任务 #${t.id}${t.name ? ' - ' + t.name : ''}`"
          :value="t.id"
        />
      </el-select>
      <el-button :icon="Refresh" size="small" @click="loadConstraints" circle />
    </div>

    <!-- Natural language input -->
    <el-card shadow="never">
      <template #header>
        <span>新增约束</span>
      </template>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder='例如: "周三下午尽量不排课，大班课优先用多媒体教室"'
          :disabled="translating"
        />
        <div style="display: flex; gap: 8px;">
          <el-button
            type="primary"
            @click="translateInput"
            :loading="translating"
            :disabled="!inputText.trim()"
          >
            {{ translating ? '翻译中...' : '翻译' }}
          </el-button>
          <el-button @click="cancelPreview" v-if="previewConstraints.length > 0">取消</el-button>
        </div>
      </div>
    </el-card>

    <!-- Translation preview -->
    <el-card v-if="previewConstraints.length > 0" shadow="never">
      <template #header>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span>LLM 理解结果 — 请确认以下约束</span>
        </div>
      </template>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div
          v-for="c in previewConstraints"
          :key="c.id"
          style="display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius);"
        >
          <el-tag :type="severityTag(c.params?.priority)" size="small">
            {{ severityLabel(c.params?.priority) }}
          </el-tag>
          <el-tag size="small">{{ c.type === 'slot_penalty' ? '时间段' : c.type === 'classroom_preference' ? '教室' : '任务关系' }}</el-tag>
          <span style="flex: 1; font-size: 13px;">
            {{ scopeLabel(c.scope) }}
            <template v-if="c.params?.slot_ids">
              · {{ c.params.slot_ids.length }} 个时间槽
            </template>
            <template v-if="c.params?.room_type">
              · 教室: {{ c.params.room_type }}
            </template>
          </span>
          <div style="font-size: 12px; color: var(--muted-foreground); max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            {{ c.source }}
          </div>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 8px;">
          <el-button type="primary" @click="applyConstraints">
            确认并生效 ({{ previewConstraints.length }} 条)
          </el-button>
          <el-button @click="cancelPreview">修改描述重新翻译</el-button>
        </div>
      </div>
    </el-card>

    <!-- Active constraints -->
    <el-card shadow="never" v-loading="constraintsLoading">
      <template #header>
        <span>生效中的约束 ({{ constraints.length }})</span>
      </template>

      <el-empty v-if="constraints.length === 0 && !constraintsLoading" description="暂无约束" />

      <div v-else style="display: flex; flex-direction: column; gap: 8px;">
        <div
          v-for="c in constraints"
          :key="c.id"
          style="display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius); opacity: c.active !== false ? 1 : 0.45;"
        >
          <el-tag :type="severityTag(c.params?.priority)" size="small">
            {{ severityLabel(c.params?.priority) }}
          </el-tag>
          <el-tag size="small">{{ c.type === 'slot_penalty' ? '时间段' : c.type === 'classroom_preference' ? '教室' : '任务关系' }}</el-tag>
          <span style="flex: 1; font-size: 13px;">
            {{ scopeLabel(c.scope) }}
            <template v-if="c.params?.slot_ids">
              · {{ c.params.slot_ids.length }} 个时间槽
            </template>
            <template v-if="c.params?.room_type">
              · 教室: {{ c.params.room_type }}
            </template>
          </span>
          <div style="font-size: 12px; color: var(--muted-foreground); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            "{{ c.source }}"
          </div>
          <div style="font-size: 11px; color: var(--muted-foreground); white-space: nowrap;">
            {{ c.active !== false ? '生效' : '暂停' }}
          </div>
          <el-button
            :icon="Switch"
            size="small"
            :type="c.active !== false ? 'warning' : 'default'"
            @click="toggleConstraint(c.id)"
            circle
          />
          <el-button
            :icon="Delete"
            size="small"
            type="danger"
            @click="deleteConstraint(c.id)"
            circle
          />
        </div>
      </div>
    </el-card>
  </div>
</template>
