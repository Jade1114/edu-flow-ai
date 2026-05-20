<script setup>
import { computed, reactive, ref } from 'vue'

const API_BASE_STORAGE_KEY = 'edu-flow-ai.viewer.apiBaseUrl'

const apiBaseUrl = ref(localStorage.getItem(API_BASE_STORAGE_KEY) || 'http://localhost:8080')
const form = reactive({
  taskId: '1',
  topK: '5',
  schemeId: '',
  teacherId: '1',
})
const loginForm = reactive({
  employeeNo: 'ADMIN001',
  password: '123456',
})

const teachers = ref([])
const loadingKey = ref('')

async function loadTeachers() {
  try {
    const resp = await fetch(`${apiBaseUrl.value.trim().replace(/\/$/, '')}/api/teachers`)
    const data = await resp.json()
    teachers.value = data?.data || []
  } catch { /* ignore */ }
}
loadTeachers()
const result = ref({
  title: '尚未请求',
  method: '',
  url: '',
  status: null,
  durationMs: null,
  ok: null,
  body: null,
  rawText: '',
  error: '',
})

const loginAction = {
  key: 'login',
  label: '登录测试',
  method: 'POST',
  path: () => '/api/auth/login',
  body: () => ({
    employeeNo: requiredText(loginForm.employeeNo, '工号'),
    password: requiredText(loginForm.password, '密码'),
  }),
}

const actions = [
  {
    group: '分课',
    key: 'generate-schemes',
    label: '生成候选方案',
    method: 'POST',
    path: () => `/api/allocation-tasks/${required(form.taskId, '分课任务 ID')}/schemes?topK=${topK()}`,
  },
  {
    group: '分课',
    key: 'task-schemes',
    label: '查询任务候选方案',
    method: 'GET',
    path: () => `/api/allocation-tasks/${required(form.taskId, '分课任务 ID')}/schemes`,
  },
  {
    group: '分课',
    key: 'confirm-scheme',
    label: '确认候选方案',
    method: 'POST',
    path: () => `/api/allocation-schemes/${required(form.schemeId, '候选方案 ID')}/confirm`,
  },
  {
    group: '课表',
    key: 'assignments',
    label: '查询正式课表',
    method: 'GET',
    path: () => '/api/course-assignments',
  },
  {
    group: '课表',
    key: 'teacher-assignments',
    label: '查询教师课表',
    method: 'GET',
    path: () => `/api/teachers/${required(form.teacherId, '教师 ID')}/course-assignments`,
  },
]

const groupedActions = computed(() => {
  return actions.reduce((groups, action) => {
    if (!groups[action.group]) {
      groups[action.group] = []
    }
    groups[action.group].push(action)
    return groups
  }, {})
})

const responseData = computed(() => {
  const body = result.value.body
  if (body && typeof body === 'object' && Object.prototype.hasOwnProperty.call(body, 'data')) {
    return body.data
  }
  return body
})

const prettyJson = computed(() => {
  if (result.value.body !== null) {
    return JSON.stringify(result.value.body, null, 2)
  }
  return result.value.rawText || ''
})

const schemes = computed(() => {
  const data = responseData.value
  if (Array.isArray(data)) {
    return data.filter((item) => item && ('schemeName' in item || 'conflictSummary' in item))
  }
  return Array.isArray(data?.schemes) ? data.schemes : []
})

const assignments = computed(() => {
  const data = responseData.value
  if (!Array.isArray(data)) {
    return []
  }
  return data.filter((item) => item && ('courseName' in item || 'timeSlotLabel' in item))
})

const promptPreview = computed(() => {
  const data = responseData.value
  if (!data || typeof data !== 'object') {
    return null
  }
  if (!data.systemPrompt && !data.userPrompt && !data.outputSchema && !data.query) {
    return null
  }
  return data
})

const loginUser = computed(() => {
  const data = responseData.value
  if (!data || typeof data !== 'object' || !('employeeNo' in data)) {
    return null
  }
  return data
})

const hasStructuredView = computed(() => {
  return (
    loginUser.value ||
    schemes.value.length > 0 ||
    assignments.value.length > 0 ||
    promptPreview.value
  )
})

async function runAction(action) {
  loadingKey.value = action.key
  const startedAt = performance.now()

  try {
    const url = buildUrl(action.path())
    const body = action.body?.()
    const options = {
      method: action.method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }

    localStorage.setItem(API_BASE_STORAGE_KEY, apiBaseUrl.value.trim())
    const response = await fetch(url, options)
    const rawText = await response.text()
    const parsedBody = parseJson(rawText)

    result.value = {
      title: action.label,
      method: action.method,
      url,
      status: response.status,
      durationMs: Math.round(performance.now() - startedAt),
      ok: response.ok,
      body: parsedBody,
      rawText,
      error: '',
    }
  } catch (error) {
    result.value = {
      title: action.label,
      method: action.method,
      url: '',
      status: null,
      durationMs: Math.round(performance.now() - startedAt),
      ok: false,
      body: null,
      rawText: '',
      error: error instanceof Error ? error.message : String(error),
    }
  } finally {
    loadingKey.value = ''
  }
}

function buildUrl(path) {
  const trimmedBase = apiBaseUrl.value.trim().replace(/\/$/, '')
  if (!trimmedBase) {
    return path
  }
  if (trimmedBase.endsWith('/api') && path.startsWith('/api/')) {
    return `${trimmedBase}${path.slice(4)}`
  }
  return `${trimmedBase}${path}`
}

function parseJson(text) {
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function required(value, label) {
  const normalized = String(value ?? '').trim()
  if (!normalized) {
    throw new Error(`${label} 不能为空`)
  }
  return encodeURIComponent(normalized)
}

function requiredText(value, label) {
  const normalized = String(value ?? '').trim()
  if (!normalized) {
    throw new Error(`${label} 不能为空`)
  }
  return normalized
}

function topK() {
  return positiveInteger(form.topK, 'TopK')
}

function positiveInteger(value, label) {
  const normalized = Number(value)
  if (!Number.isInteger(normalized) || normalized < 1) {
    throw new Error(`${label} 必须是正整数`)
  }
  return normalized
}

function tableValue(value) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function pickRows(rows, keys) {
  return rows.map((row) => {
    return keys.reduce((picked, key) => {
      picked[key] = row?.[key]
      return picked
    }, {})
  })
}
</script>

<template>
  <main class="viewer-shell">
    <section class="topbar">
      <div>
        <p class="eyebrow">Edu Flow AI</p>
        <h1>接口结果查看页</h1>
      </div>
      <label class="api-base">
        <span>API Base URL</span>
        <input v-model="apiBaseUrl" type="text" autocomplete="off" />
      </label>
    </section>

    <section class="workspace">
      <aside class="controls-panel">
        <section class="login-test">
          <h2>登录测试</h2>
          <div class="login-grid">
            <label>
              <span>工号</span>
              <input v-model="loginForm.employeeNo" type="text" autocomplete="username" />
            </label>
            <label>
              <span>密码</span>
              <input v-model="loginForm.password" type="password" autocomplete="current-password" />
            </label>
          </div>
          <button
            type="button"
            class="login-button"
            :disabled="Boolean(loadingKey)"
            @click="runAction(loginAction)"
          >
            <span class="method">POST</span>
            <span>{{ loadingKey === loginAction.key ? '请求中...' : '调用登录接口' }}</span>
          </button>
        </section>

        <div class="field-grid">
          <label>
            <span>分课任务 ID</span>
            <input v-model="form.taskId" type="number" min="1" />
          </label>
          <label>
            <span>TopK</span>
            <input v-model="form.topK" type="number" min="1" max="20" />
          </label>
          <label>
            <span>候选方案 ID</span>
            <input v-model="form.schemeId" type="number" min="1" />
          </label>
          <label>
            <span>教师</span>
            <select v-model="form.teacherId">
              <option v-for="t in teachers" :key="t.id" :value="t.id">{{ t.name }}（#{{ t.id }}）</option>
            </select>
          </label>
        </div>

        <div class="action-groups">
          <section v-for="(groupActions, groupName) in groupedActions" :key="groupName" class="action-group">
            <h2>{{ groupName }}</h2>
            <button
              v-for="action in groupActions"
              :key="action.key"
              type="button"
              :disabled="Boolean(loadingKey)"
              @click="runAction(action)"
            >
              <span class="method">{{ action.method }}</span>
              <span>{{ loadingKey === action.key ? '请求中...' : action.label }}</span>
            </button>
          </section>
        </div>
      </aside>

      <section class="result-panel">
        <header class="result-header">
          <div>
            <p class="eyebrow">Response</p>
            <h2>{{ result.title }}</h2>
          </div>
          <div v-if="result.status !== null" class="status-row">
            <span :class="['status-pill', result.ok ? 'success' : 'error']">{{ result.status }}</span>
            <span>{{ result.durationMs }} ms</span>
          </div>
        </header>

        <p v-if="result.url" class="request-url">{{ result.method }} {{ result.url }}</p>
        <p v-if="result.error" class="error-box">{{ result.error }}</p>

        <section v-if="hasStructuredView" class="structured-view">
          <section v-if="loginUser" class="login-result">
            <h3>登录返回</h3>
            <div class="detail-grid">
              <span>工号</span>
              <strong>{{ tableValue(loginUser.employeeNo) }}</strong>
              <span>姓名</span>
              <strong>{{ tableValue(loginUser.displayName || loginUser.name) }}</strong>
              <span>角色</span>
              <strong>{{ tableValue(loginUser.role) }}</strong>
              <span>教师 ID</span>
              <strong>{{ tableValue(loginUser.teacherId) }}</strong>
              <span>部门</span>
              <strong>{{ tableValue(loginUser.department) }}</strong>
              <span>职称</span>
              <strong>{{ tableValue(loginUser.title) }}</strong>
            </div>
          </section>

          <div v-if="promptPreview" class="prompt-grid">
            <article v-if="promptPreview.query" class="text-block">
              <h3>Query</h3>
              <pre>{{ promptPreview.query }}</pre>
            </article>
            <article v-if="promptPreview.systemPrompt" class="text-block">
              <h3>System Prompt</h3>
              <pre>{{ promptPreview.systemPrompt }}</pre>
            </article>
            <article v-if="promptPreview.userPrompt" class="text-block">
              <h3>User Prompt</h3>
              <pre>{{ promptPreview.userPrompt }}</pre>
            </article>
            <article v-if="promptPreview.outputSchema" class="text-block">
              <h3>Output Schema</h3>
              <pre>{{ promptPreview.outputSchema }}</pre>
            </article>
          </div>


          <section v-if="schemes.length" class="table-section">
            <h3>候选方案</h3>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>分数</th>
                  <th>有效</th>
                  <th>状态</th>
                  <th>冲突摘要</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="scheme in pickRows(schemes, [
                    'id',
                    'schemeName',
                    'score',
                    'valid',
                    'status',
                    'conflictSummary',
                  ])"
                  :key="scheme.id || scheme.schemeName"
                >
                  <td>{{ tableValue(scheme.id) }}</td>
                  <td>{{ tableValue(scheme.schemeName) }}</td>
                  <td>{{ tableValue(scheme.score) }}</td>
                  <td>{{ tableValue(scheme.valid) }}</td>
                  <td>{{ tableValue(scheme.status) }}</td>
                  <td>{{ tableValue(scheme.conflictSummary) }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="assignments.length" class="table-section">
            <h3>正式课表</h3>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>课程</th>
                  <th>班级</th>
                  <th>教师</th>
                  <th>教室</th>
                  <th>时间</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="assignment in pickRows(assignments, [
                    'id',
                    'courseName',
                    'classGroupName',
                    'teacherName',
                    'classroomName',
                    'timeSlotLabel',
                    'status',
                  ])"
                  :key="assignment.id"
                >
                  <td>{{ tableValue(assignment.id) }}</td>
                  <td>{{ tableValue(assignment.courseName) }}</td>
                  <td>{{ tableValue(assignment.classGroupName) }}</td>
                  <td>{{ tableValue(assignment.teacherName) }}</td>
                  <td>{{ tableValue(assignment.classroomName) }}</td>
                  <td>{{ tableValue(assignment.timeSlotLabel) }}</td>
                  <td>{{ tableValue(assignment.status) }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <pre>{{ prettyJson || '点击左侧按钮后显示响应内容' }}</pre>
        </section>
      </section>
    </section>
  </main>
</template>

<style scoped>
.viewer-shell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.topbar h1 {
  margin: 4px 0 0;
  font-size: 24px;
}
.eyebrow {
  margin: 0;
  font-size: 12px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.api-base {
  display: flex;
  align-items: center;
  gap: 8px;
}
.api-base input {
  width: 260px;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}
.workspace {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
}
.controls-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.login-test {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}
.login-test h2 {
  margin: 0 0 12px;
  font-size: 16px;
}
.login-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 10px;
}
.login-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #606266;
}
.login-grid input {
  padding: 6px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}
.login-button {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 6px;
  background: #409eff;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
}
.login-button:hover {
  background: #66b1ff;
}
.login-button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #606266;
}
.field-grid input {
  padding: 6px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}
.wide-field {
  grid-column: 1 / -1;
}
.action-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.action-group {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
}
.action-group h2 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #303133;
}
.action-group button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin-bottom: 8px;
  padding: 8px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}
.action-group button:hover {
  border-color: #409eff;
  color: #409eff;
}
.action-group button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.method {
  display: inline-block;
  min-width: 44px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e6f2ff;
  color: #409eff;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
}
.result-panel {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 20px;
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.result-header h2 {
  margin: 4px 0 0;
  font-size: 18px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #606266;
}
.status-pill {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.status-pill.success {
  background: #e1f3d8;
  color: #67c23a;
}
.status-pill.error {
  background: #fde2e2;
  color: #f56c6c;
}
.request-url {
  font-size: 13px;
  color: #909399;
  margin-bottom: 16px;
  word-break: break-all;
}
.error-box {
  background: #fde2e2;
  color: #f56c6c;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 16px;
}
.structured-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 20px;
}
.login-result {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}
.login-result h3 {
  margin: 0 0 12px;
  font-size: 14px;
}
.detail-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 16px;
  font-size: 13px;
}
.detail-grid span {
  color: #606266;
}
.prompt-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.text-block {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}
.text-block h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.text-block pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.cards-section {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}
.cards-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
}
.teacher-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}
.teacher-card {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  font-size: 13px;
}
.teacher-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.teacher-card p {
  margin: 4px 0;
  color: #606266;
}
.teacher-card .muted {
  color: #909399;
  font-size: 12px;
}
.table-section {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
}
.table-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid #e4e7ed;
}
th {
  color: #606266;
  font-weight: 600;
  background: #fff;
}
.raw-json {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  padding: 16px;
}
.raw-json pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
}
.section-title h3 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #fff;
}
</style>
