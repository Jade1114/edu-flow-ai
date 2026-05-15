<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import request from "@/api/request.js";
import { ElMessage, ElMessageBox } from "element-plus";
import { ActiveStatus, SchemeStatus } from "@/constants/status.js";

const tasks = ref([]);
const taskDialog = ref(false);
const taskForm = ref({
  id: null,
  name: "",
  description: "",
  startWeek: 1,
  endWeek: 18,
  teachingTaskIds: [],
});

const schemes = ref([]);
const schemeVisible = ref(false);
const currentTaskId = ref(null);

const generating = ref(false);
const genStatus = ref(null);
const genProgress = ref(0);
let pollTimer = null;
let generationSource = null;
const topK = ref(5);
const policy = ref('BALANCED');

const policyOptions = [
  { value: 'BALANCED', label: '综合平衡' },
  { value: 'TEACHER_FRIENDLY', label: '教师友好' },
  { value: 'CLASS_BALANCED', label: '班级均衡' },
  { value: 'ROOM_EFFICIENT', label: '教室利用' },
  { value: 'COMPACT', label: '紧凑排课' },
];

const teachingTasks = ref([]);

async function loadTasks() {
  tasks.value = await request.get("/api/allocation-tasks");
}

async function loadTeachingTasks() {
  teachingTasks.value = await request.get(
    `/api/teaching-tasks?status=${ActiveStatus.ACTIVE}`,
  );
}

function openTaskDialog(row) {
  if (row) {
    taskForm.value = {
      id: row.id,
      name: row.name || "",
      description: row.description || "",
      startWeek: row.startWeek || 1,
      endWeek: row.endWeek || 18,
      teachingTaskIds: row.teachingTasks
        ? row.teachingTasks.map((tt) => tt.id)
        : [],
    };
  } else {
    taskForm.value = {
      id: null,
      name: "",
      description: "",
      startWeek: 1,
      endWeek: 18,
      teachingTaskIds: [],
    };
  }
  taskDialog.value = true;
  // 对话框渲染后恢复表格勾选状态
  nextTick(() => {
    if (!taskTableRef.value) return
    taskTableRef.value.clearSelection()
    const selectedIds = taskForm.value.teachingTaskIds
    teachingTasks.value.forEach(tt => {
      if (selectedIds.includes(tt.id)) {
        taskTableRef.value.toggleRowSelection(tt, true)
      }
    })
  })
}

const taskTableRef = ref()

function handleTaskSelectionChange(selection) {
  taskForm.value.teachingTaskIds = selection.map(tt => tt.id)
}

function selectAllTasks() {
  taskForm.value.teachingTaskIds = teachingTasks.value.map(tt => tt.id)
  // 同步表格勾选状态
  if (taskTableRef.value) {
    teachingTasks.value.forEach(tt => taskTableRef.value.toggleRowSelection(tt, true))
  }
}

function clearAllTasks() {
  taskForm.value.teachingTaskIds = []
  if (taskTableRef.value) {
    taskTableRef.value.clearSelection()
  }
}

async function saveTask() {
  if (!taskForm.value.name) {
    ElMessage.warning("请输入任务名称");
    return;
  }
  if (taskForm.value.teachingTaskIds.length === 0) {
    ElMessage.warning("请至少选择一个教学任务");
    return;
  }
  const payload = { ...taskForm.value };
  if (payload.id) {
    await request.put(`/api/allocation-tasks/${payload.id}`, payload);
  } else {
    await request.post("/api/allocation-tasks", payload);
  }
  ElMessage.success("保存成功");
  taskDialog.value = false;
  loadTasks();
}

async function viewSchemes(taskId) {
  currentTaskId.value = taskId;
  schemes.value = await request.get(`/api/allocation-tasks/${taskId}/schemes`);
  schemeVisible.value = true;
}

async function generateSchemes(taskId) {
  stopGenerationListeners();
  generating.value = true;
  genProgress.value = 10;
  genStatus.value = { stage: "running", status: "RUNNING", message: "开始生成..." };
  currentTaskId.value = taskId;

  try {
    await request.post(`/api/allocation-tasks/${taskId}/generate-async?topK=${topK.value}&policy=${policy.value}`);
    startSse(taskId);
  } catch (e) {
    generating.value = false;
    genStatus.value = { stage: "error", status: "FAILED", message: e.message };
    ElMessage.error("启动生成失败");
  }
}

function stageLabel(stage) {
  const labels = {
    ml: '调用自训练模型...',
    eval: '评估方案质量...',
    rag: '检索画像...',
    prompt: '构建 Prompt...',
    llm: '等待模型...',
    parse: '解析结果...',
    persist: '保存方案...',
    conflict: '检测冲突...',
    running: '生成中...',
    done: '生成完成',
    error: '生成失败',
  };
  return labels[stage] || '生成中...';
}

function applyGenerationStatus(taskId, status) {
  const isCompleted = status.status === "COMPLETED";
  const isFailed = status.status === "FAILED";
  const stage = isCompleted ? "done" : isFailed ? "error" : (status.stage || "running");
  genProgress.value = Number.isFinite(status.progress) ? status.progress : (isCompleted || isFailed ? 100 : 50);
  genStatus.value = {
    ...status,
    stage,
    message: isCompleted
      ? `生成完成，共 ${status.schemeCount || 0} 个方案`
      : isFailed
        ? `生成失败: ${status.error || "未知错误"}`
        : (status.message || "自训练模型正在生成分课方案..."),
  };

  if (isCompleted) {
    stopGenerationListeners();
    generating.value = false;
    ElMessage.success(`生成完成，共 ${status.schemeCount || 0} 个方案`);
    viewSchemes(taskId);
  } else if (isFailed) {
    stopGenerationListeners();
    generating.value = false;
    ElMessage.error(`生成失败: ${status.error || "未知错误"}`);
  }
}

function startSse(taskId) {
  if (!window.EventSource) {
    startPolling(taskId);
    return;
  }
  generationSource = new EventSource(`/api/allocation-tasks/${taskId}/generation-stream`);
  generationSource.addEventListener("status", (event) => {
    applyGenerationStatus(taskId, JSON.parse(event.data));
  });
  generationSource.onerror = () => {
    if (!generating.value) return;
    closeGenerationSource();
    startPolling(taskId);
  };
}

function startPolling(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const status = await request.get(`/api/allocation-tasks/${taskId}/generation-status`);
      applyGenerationStatus(taskId, status);
    } catch (e) {
      stopGenerationListeners();
      generating.value = false;
      genStatus.value = { stage: "error", status: "FAILED", message: e.message };
    }
  }, 2000);
}

function closeGenerationSource() {
  if (generationSource) {
    generationSource.close();
    generationSource = null;
  }
}

function stopGenerationListeners() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  closeGenerationSource();
}

async function confirmScheme(schemeId) {
  await ElMessageBox.confirm("确认将此方案设为正式课表？", "提示", {
    type: "warning",
  });
  await request.post(`/api/allocation-schemes/${schemeId}/confirm`);
  ElMessage.success("确认成功");
  detailVisible.value = false;
  viewSchemes(currentTaskId.value);
  loadTasks();
}

// === 课程表视图 ===

const detailVisible = ref(false);
const schemeDetail = ref(null);
const currentWeek = ref(1);
const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const weekItems = computed(() => {
  if (!schemeDetail.value?.items) return [];
  return schemeDetail.value.items.filter(
    (item) => item.weekNumber === currentWeek.value,
  );
});

function itemsAtSlot(dayOfWeek, periodIndex) {
  return weekItems.value.filter(
    (item) => item.dayOfWeek === dayOfWeek && item.periodIndex === periodIndex,
  );
}

const slotDetail = ref({ visible: false, items: [], dayOfWeek: null, periodIndex: null });

function openSlotDetail(dayOfWeek, periodIndex) {
  const items = itemsAtSlot(dayOfWeek, periodIndex);
  if (items.length === 0) return;
  slotDetail.value = {
    visible: true,
    items,
    dayOfWeek: dayNames[dayOfWeek - 1],
    periodIndex,
  };
}

// === 手动编辑排课片段 ===
const editDialog = ref(false);
const editingItem = ref(null);
const classrooms = ref([]);
const timeSlots = ref([]);
const savingMove = ref(false);

async function loadClassrooms() {
  classrooms.value = await request.get(`/api/classrooms?status=${ActiveStatus.ACTIVE}`);
}

async function loadTimeSlots() {
  timeSlots.value = await request.get('/api/time-slots');
}

function openEditDialog(item) {
  editingItem.value = { ...item };
  editDialog.value = true;
  loadClassrooms();
  loadTimeSlots();
}

function timeSlotLabel(ts) {
  return `第${ts.weekNumber}周 周${['一','二','三','四','五','六','日'][ts.dayOfWeek - 1]} 第${ts.periodIndex}节`;
}

async function saveItemMove() {
  const item = editingItem.value;
  if (!item.classroomId || !item.timeSlotId) {
    ElMessage.warning('请选择教室和时间段');
    return;
  }
  savingMove.value = true;
  try {
    await request.put(`/api/allocation-schemes/${schemeDetail.value.id}/items/${item.id}`, {
      classroomId: item.classroomId,
      timeSlotId: item.timeSlotId,
    });
    ElMessage.success('修改成功，已重新检测冲突');
    editDialog.value = false;
    // 刷新 schemeDetail 完整数据（含 conflictSummary）+ items
    const [detail, items] = await Promise.all([
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}`),
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}/items`),
    ]);
    schemeDetail.value = { ...schemeDetail.value, ...detail, items };
    // 同步刷新 slot 详情弹窗
    const dayIndex = ['周一','周二','周三','周四','周五','周六','周日'].indexOf(slotDetail.value.dayOfWeek) + 1;
    if (dayIndex > 0 && slotDetail.value.periodIndex != null) {
      slotDetail.value = {
        ...slotDetail.value,
        items: items.filter(i => i.weekNumber === currentWeek.value
          && i.dayOfWeek === dayIndex
          && i.periodIndex === slotDetail.value.periodIndex),
      };
    }
  } finally {
    savingMove.value = false;
  }
}

// === 拖拽调整排课 ===
const dragItem = ref(null);
const dropTarget = ref(null); // 'day-period' string for highlighting
let timeSlotMap = {}; // "weekNumber-dayOfWeek-periodIndex" → timeSlotId
const draggingEnabled = ref(true);

function buildTimeSlotMap(slots) {
  timeSlotMap = {};
  for (const ts of slots) {
    timeSlotMap[`${ts.weekNumber}-${ts.dayOfWeek}-${ts.periodIndex}`] = ts.id;
  }
}

function onDragStart(e, item) {
  dragItem.value = item;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', String(item.id));
}

function onDragOver(e, day, period) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  dropTarget.value = `${day}-${period}`;
}

function onDragLeave() {
  dropTarget.value = null;
}

async function onDrop(e, day, period) {
  e.preventDefault();
  dropTarget.value = null;
  const item = dragItem.value;
  if (!item) return;

  const key = `${currentWeek.value}-${day}-${period}`;
  const targetTimeSlotId = timeSlotMap[key];
  if (!targetTimeSlotId) {
    ElMessage.warning('该时间段不存在');
    return;
  }
  if (targetTimeSlotId === item.timeSlotId) {
    dragItem.value = null;
    return; // 没变化
  }

  // 调 API
  savingMove.value = true;
  try {
    await request.put(`/api/allocation-schemes/${schemeDetail.value.id}/items/${item.id}`, {
      classroomId: item.classroomId,
      timeSlotId: targetTimeSlotId,
    });
    ElMessage.success('已移动');
    // 刷新 scheme 完整数据（含 conflictSummary）+ items
    const [detail, items] = await Promise.all([
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}`),
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}/items`),
    ]);
    schemeDetail.value = { ...schemeDetail.value, ...detail, items };
  } catch (e) {
    ElMessage.error('移动失败');
  } finally {
    savingMove.value = false;
    dragItem.value = null;
  }
}

async function viewSchemeDetail(schemeId) {
  const [detail, items, allTimeSlots] = await Promise.all([
    request.get(`/api/allocation-schemes/${schemeId}`),
    request.get(`/api/allocation-schemes/${schemeId}/items`),
    request.get('/api/time-slots'),
  ]);
  // 从任务列表中找到对应任务的周次范围
  const task = tasks.value.find((t) => t.id === detail.taskId);
  buildTimeSlotMap(allTimeSlots);
  schemeDetail.value = { ...detail, items, taskStartWeek: task?.startWeek || 1, taskEndWeek: task?.endWeek || 18 };
  currentWeek.value = task?.startWeek || 1;
  detailVisible.value = true;
}

onMounted(() => {
  loadTasks();
  loadTeachingTasks();
});

onUnmounted(() => {
  stopGenerationListeners();
});
</script>

<template>
  <div>
    <h2>分课任务管理</h2>
    <div style="margin: 16px 0; display: flex; gap: 12px; align-items: center">
      <el-button type="primary" @click="openTaskDialog()">新建任务</el-button>
      <span style="color: #909399; font-size: 13px">策略：</span>
      <el-select v-model="policy" size="small" style="width: 110px">
        <el-option v-for="p in policyOptions" :key="p.value" :label="p.label" :value="p.value" />
      </el-select>
      <span style="color: #909399; font-size: 13px">TopK：</span>
      <div v-if="generating" style="flex: 1; max-width: 300px">
        <el-progress
          :percentage="genProgress"
          :status="genStatus?.stage === 'error' ? 'exception' : undefined"
          :text-inside="true"
          :stroke-width="20"
        >
          <span>{{ genStatus?.message || '' }}</span>
        </el-progress>
      </div>
      <el-input-number
        v-model="topK"
        :min="1"
        :max="20"
        size="small"
        style="width: 100px"
      />
    </div>

    <el-table :data="tasks" border size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="任务名称" />
      <el-table-column label="周次范围" width="120">
        <template #default="{ row }">
          第 {{ row.startWeek }} ~ {{ row.endWeek }} 周
        </template>
      </el-table-column>
      <el-table-column label="教学任务数" width="100">
        <template #default="{ row }">
          {{ row.teachingTasks?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="createdBy" label="创建人" width="100" />
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openTaskDialog(row)"
            >编辑</el-button
          >
          <el-button
            type="success"
            size="small"
            :loading="generating"
            :disabled="generating"
            @click="generateSchemes(row.id)"
          >
            {{ generating ? (genStatus?.stage ? stageLabel(genStatus.stage) : '生成中...') : '生成方案' }}
          </el-button>
          <el-button type="info" size="small" @click="viewSchemes(row.id)"
            >查看方案</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <!-- Task Dialog -->
    <el-dialog
      v-model="taskDialog"
      :title="taskForm.id ? '编辑任务' : '新建任务'"
      width="720px"
    >
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="taskForm.name" />
        </el-form-item>
        <el-form-item label="周次范围">
          <div style="display: flex; gap: 8px; align-items: center">
            <el-input-number v-model="taskForm.startWeek" :min="1" :max="18" />
            <span>~</span>
            <el-input-number v-model="taskForm.endWeek" :min="1" :max="18" />
          </div>
        </el-form-item>
        <el-form-item label="教学任务">
          <div style="margin-bottom: 8px; display: flex; gap: 8px; align-items: center;">
            <el-button size="small" @click="selectAllTasks">全选</el-button>
            <el-button size="small" @click="clearAllTasks">清空</el-button>
            <span style="font-size: 12px; color: #909399;">
              已选 {{ taskForm.teachingTaskIds.length }} 个
            </span>
          </div>
          <el-table
            ref="taskTableRef"
            :data="teachingTasks"
            border
            size="small"
            max-height="320"
            style="width: 100%"
            @selection-change="handleTaskSelectionChange"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column prop="course.name" label="课程" width="130" />
            <el-table-column prop="primaryTeacher.name" label="教师" width="80" />
            <el-table-column label="班级" width="150">
              <template #default="{ row }">
                {{ row.classGroups?.map(cg => cg.name).join(', ') || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="totalHours" label="课时" width="60" />
            <el-table-column label="教室" width="100">
              <template #default="{ row }">
                {{ row.classroom?.name || '-' }}
              </template>
            </el-table-column>
          </el-table>
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
    <el-dialog v-model="schemeVisible" title="候选方案" width="900px">
      <el-table :data="schemes" border size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="schemeName" label="方案名称" />
        <el-table-column prop="schemeScore" label="评分" width="70">
          <template #default="{ row }">
            <span v-if="row.schemeScore != null" style="font-weight: 700; color: #67c23a">
              {{ row.schemeScore.toFixed(1) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="policy" label="策略" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.policy" size="small" type="info">{{ row.policy }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="valid" label="有效" width="70">
          <template #default="{ row }">
            <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{
              row.valid ? "是" : "否"
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column
          prop="conflictSummary"
          label="冲突摘要"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click="viewSchemeDetail(row.id)"
              >详情</el-button
            >
            <el-button
              type="success"
              size="small"
              :disabled="!row.valid"
              @click="confirmScheme(row.id)"
              >{{ row.status === SchemeStatus.CONFIRMED ? '重新确认' : '确认' }}</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- Scheme Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      title="方案详情"
      width="95%"
      max-width="1200px"
    >
      <div v-if="schemeDetail">
        <div
          style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
          "
        >
          <div>
            <strong>{{ schemeDetail.schemeName }}</strong>
            <span style="color: #909399; font-size: 13px; margin-left: 12px">
              {{ schemeDetail.summary }}
            </span>
          </div>
          <div>
            <el-tag v-if="schemeDetail.conflictSummary" type="danger" size="small"
              >冲突: {{ schemeDetail.conflictSummary }}</el-tag
            >
            
          </div>
        </div>

        <!-- 周次分页 -->
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px">
          <el-button
            :disabled="currentWeek <= 1"
            size="small"
            @click="currentWeek--"
            >‹ 上一周</el-button
          >
          <span style="font-weight: bold; font-size: 15px"
            >第 {{ currentWeek }} 周</span
          >
          <el-button
            :disabled="currentWeek >= 18"
            size="small"
            @click="currentWeek++"
            >下一周 ›</el-button
          >
          <span style="color: #909399; font-size: 13px; margin-left: 8px">
            （本周 {{ weekItems.length }} 个排课片段）
          </span>
        </div>

        <!-- 课程表表格 -->
        <div style="overflow-x: auto">
          <table
            class="timetable"
            style="width: 100%; border-collapse: collapse; font-size: 13px"
          >
            <thead>
              <tr>
                <th
                  style="
                    width: 70px;
                    padding: 8px 4px;
                    border: 1px solid var(--border, #dcdfe6);
                    background: var(--el-fill-color-light, #f5f7fa);
                    text-align: center;
                  "
                >
                  节次
                </th>
                <th
                  v-for="day in dayNames"
                  :key="day"
                  style="
                    padding: 8px 4px;
                    border: 1px solid var(--border, #dcdfe6);
                    background: var(--el-fill-color-light, #f5f7fa);
                    text-align: center;
                    min-width: 130px;
                  "
                >
                  {{ day }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="period in 5" :key="period">
                <td
                  style="
                    padding: 8px 4px;
                    border: 1px solid var(--border, #dcdfe6);
                    text-align: center;
                    font-weight: bold;
                    background: var(--el-fill-color-light, #f5f7fa);
                  "
                >
                  第{{ period }}节
                </td>
                <td
                  v-for="day in 7"
                  :key="day"
                  style="
                    padding: 4px;
                    border: 1px solid var(--border, #dcdfe6);
                    vertical-align: top;
                    cursor: pointer;
                    min-height: 60px;
                    height: auto;
                    transition: background 0.15s;
                  "
                  :class="{
                    'slot-hover': itemsAtSlot(day, period).length > 0,
                    'drop-highlight': dropTarget === `${day}-${period}`,
                  }"
                  @click="openSlotDetail(day, period)"
                  @dragover="onDragOver($event, day, period)"
                  @dragleave="onDragLeave"
                  @drop="onDrop($event, day, period)"
                >
                  <div v-if="itemsAtSlot(day, period).length > 0" style="display: flex; flex-direction: column; gap: 3px">
                    <div
                      v-for="item in itemsAtSlot(day, period)"
                      :key="item.id"
                      draggable="true"
                      :style="{
                        padding: '3px 5px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        lineHeight: '1.4',
                        background: item.valid === false ? 'var(--el-color-danger-light-9, #fef0f0)' : 'var(--el-color-primary-light-9, #ecf5ff)',
                        color: item.valid === false ? 'var(--el-color-danger, #f56c6c)' : 'var(--el-color-primary, #409eff)',
                        cursor: 'grab',
                      }""
                      @dragstart="onDragStart($event, item)"
                      @click.stop="openSlotDetail(day, period)"
                    >
                      <div style="font-weight: 600">{{ item.courseName }}</div>
                      <div :style="{ color: item.valid === false ? '#c45656' : '#666' }">{{ item.classroomName }} · {{ item.teacherName }}</div>
                      <div style="color: #999; font-size: 11px">{{ item.classGroupName }}</div>
                    </div>
                  </div>
                  <div v-else
                    style="color: #ccc; text-align: center; font-size: 11px; line-height: 40px"
                    @dragover="onDragOver($event, day, period)"
                    @dragleave="onDragLeave"
                    @drop="onDrop($event, day, period)"
                  >
                    空
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          type="success"
          :disabled="!schemeDetail?.valid"
          @click="confirmScheme(schemeDetail.id)"
        >{{ schemeDetail?.status === SchemeStatus.CONFIRMED ? '重新确认' : '确认方案' }}</el-button>
      </template>
    </el-dialog>

    <!-- Slot Detail Dialog -->
    <el-dialog
      v-model="slotDetail.visible"
      :title="`${slotDetail.dayOfWeek} 第${slotDetail.periodIndex}节 - 详情`"
      width="600px"
    >
      <el-table :data="slotDetail.items" border size="small">
        <el-table-column prop="courseName" label="课程" />
        <el-table-column prop="teacherName" label="教师" />
        <el-table-column prop="classGroupName" label="班级" />
        <el-table-column prop="classroomName" label="教室" />
        <el-table-column prop="valid" label="有效" width="60">
          <template #default="{ row }">
            <el-tag
              :type="row.valid ? 'success' : 'danger'"
              size="small"
              >{{ row.valid ? "是" : "否" }}</el-tag
            >
          </template>
        </el-table-column>
        <el-table-column
          v-if="slotDetail.items.some((i) => i.conflictMessage)"
          prop="conflictMessage"
          label="冲突"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 编辑排课片段对话框 -->
    <el-dialog v-model="editDialog" title="编辑排课片段" width="500px">
      <el-form v-if="editingItem" :model="editingItem" label-width="100px">
        <el-form-item label="课程">
          <el-input :model-value="editingItem.courseName" disabled />
        </el-form-item>
        <el-form-item label="教师">
          <el-input :model-value="editingItem.teacherName" disabled />
        </el-form-item>
        <el-form-item label="班级">
          <el-input :model-value="editingItem.classGroupName" disabled />
        </el-form-item>
        <el-form-item label="当前教室">
          <el-input :model-value="editingItem.classroomName" disabled />
        </el-form-item>
        <el-form-item label="时间段">
          <el-select v-model="editingItem.timeSlotId" filterable placeholder="选择时间段" style="width: 100%">
            <el-option
              v-for="ts in timeSlots"
              :key="ts.id"
              :label="timeSlotLabel(ts)"
              :value="ts.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingMove" @click="saveItemMove">保存</el-button>
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
.drop-highlight {
  background: var(--el-color-success-light-7, #e1f3d8) !important;
}
[draggable="true"]:active {
  opacity: 0.5;
}
.timetable td,
.timetable th {
  border-color: var(--el-border-color-light, #dcdfe6);
}
</style>
