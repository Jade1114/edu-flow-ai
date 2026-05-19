<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import request from "@/api/request.js";
import { ElMessage, ElMessageBox } from "element-plus";
import { ActiveStatus, SchemeStatus } from "@/constants/status.js";

const tasks = ref([]);
const taskDialog = ref(false);
const defaultGenerationConfig = () => ({
  allowedWeeks: Array.from({ length: 18 }, (_, index) => index + 1),
  allowedWeekdays: [1, 2, 3, 4, 5],
  allowedPeriods: [1, 2, 3, 4],
  schemeCount: 3,
  teacherProfilePenaltyScale: 50,
  distributionPenaltyScale: 5,
  classroomStickinessWeight: 5,
  compactBonusWeight: 0,
  weekdayLoadPenalty: 0.008,
  roomDayLoadPenalty: 0.005,
  roomWeekLoadPenalty: 0.002,
  taskDayLoadPenalty: 0.012,
  earlyPeriodPenalty: 0.012,
  latePeriodPenalty: 0.008,
  randomJitter: 0.002,
  classroomStickinessBonus: 0.006,
  weekendPenalty: 0.01,
  llmPrompt: "",
  llmResultJson: "",
});

const taskForm = ref({
  id: null,
  name: "",
  description: "",
  startWeek: 1,
  endWeek: 18,
  teachingTaskIds: [],
  generationConfig: defaultGenerationConfig(),
});

const weekOptions = Array.from({ length: 18 }, (_, index) => index + 1);
const weekdayOptions = [
  { label: "周一", value: 1 },
  { label: "周二", value: 2 },
  { label: "周三", value: 3 },
  { label: "周四", value: 4 },
  { label: "周五", value: 5 },
  { label: "周六", value: 6 },
  { label: "周日", value: 7 },
];
const periodOptions = [
  { label: "第1节", value: 1 },
  { label: "第2节", value: 2 },
  { label: "第3节", value: 3 },
  { label: "第4节", value: 4 },
  { label: "第5节", value: 5 },
];

const schemes = ref([]);
const schemeVisible = ref(false);
const currentTaskId = ref(null);
const generateConfirmVisible = ref(false);
const generateTargetTask = ref(null);

const generating = ref(false);
const genStatus = ref(null);
const genProgress = ref(0);
let pollTimer = null;
let generationSource = null;
const schemeCount = ref(3);
const policy = ref("BALANCED");

const policyOptions = [
  { value: "BALANCED", label: "综合平衡", desc: "均衡所有维度的默认策略" },
  {
    value: "TEACHER_FRIENDLY",
    label: "教师友好",
    desc: "避免早课和晚课，减少教师单日过载",
  },
  {
    value: "CLASS_BALANCED",
    label: "班级均衡",
    desc: "强调班级每日课时均匀分布",
  },
  {
    value: "ROOM_EFFICIENT",
    label: "教室利用",
    desc: "最大化教室使用效率，减少空闲",
  },
  { value: "COMPACT", label: "紧凑排课", desc: "压缩到更少天数，留出整块空闲" },
  {
    value: "CUSTOM",
    label: "自定义",
    desc: "手动调整或 LLM 生成的自定义权重配置",
  },
];
const policyLabelMap = {
  ...Object.fromEntries(policyOptions.map((item) => [item.value, item.label])),
  CUSTOM: "自定义",
};

// === 预设权重（与 Python POLICY_PROFILES 保持一致）===
const PRESET_WEIGHTS = {
  BALANCED: {
    weekend_penalty: 0.01,
    weekday_load_penalty: 0.008,
    room_day_load_penalty: 0.005,
    room_week_load_penalty: 0.002,
    task_day_load_penalty: 0.012,
    early_period_penalty: 0.012,
    late_period_penalty: 0.008,
    compact_bonus_weight: 0.0,
    random_jitter: 0.002,
    classroom_stickiness_bonus: 0.006,
  },
  TEACHER_FRIENDLY: {
    weekend_penalty: 0.015,
    weekday_load_penalty: 0.006,
    room_day_load_penalty: 0.004,
    room_week_load_penalty: 0.001,
    task_day_load_penalty: 0.025,
    early_period_penalty: 0.04,
    late_period_penalty: 0.03,
    compact_bonus_weight: 0.0,
    random_jitter: 0.001,
    classroom_stickiness_bonus: 0.004,
  },
  CLASS_BALANCED: {
    weekend_penalty: 0.01,
    weekday_load_penalty: 0.012,
    room_day_load_penalty: 0.004,
    room_week_load_penalty: 0.001,
    task_day_load_penalty: 0.008,
    early_period_penalty: 0.01,
    late_period_penalty: 0.01,
    compact_bonus_weight: 0.0,
    random_jitter: 0.002,
    classroom_stickiness_bonus: 0.005,
  },
  ROOM_EFFICIENT: {
    weekend_penalty: 0.01,
    weekday_load_penalty: 0.002,
    room_day_load_penalty: 0.025,
    room_week_load_penalty: 0.01,
    task_day_load_penalty: 0.005,
    early_period_penalty: 0.005,
    late_period_penalty: 0.005,
    compact_bonus_weight: 0.0,
    random_jitter: 0.003,
    classroom_stickiness_bonus: 0.008,
  },
  COMPACT: {
    weekend_penalty: 0.005,
    weekday_load_penalty: 0.002,
    room_day_load_penalty: 0.008,
    room_week_load_penalty: 0.002,
    task_day_load_penalty: 0.01,
    early_period_penalty: 0.005,
    late_period_penalty: 0.005,
    compact_bonus_weight: 0.015,
    random_jitter: 0.002,
    classroom_stickiness_bonus: 0.003,
  },
};

const weightLabels = {
  teacher_profile_penalty_scale: "教师画像权重",
  distribution_penalty_scale: "分布均衡权重",
  classroom_stickiness_weight: "教室粘性权重",
  compact_bonus_weight: "紧凑奖励权重",
  weekday_load_penalty: "星期均衡惩罚",
  room_day_load_penalty: "教室日负载",
  room_week_load_penalty: "教室周负载",
  task_day_load_penalty: "单日集中惩罚",
  early_period_penalty: "早课惩罚",
  late_period_penalty: "晚课惩罚",
  random_jitter: "随机扰动",
  classroom_stickiness_bonus: "教室粘性奖励",
  weekend_penalty: "周末惩罚",
};

const weightDescs = {
  weekday_load_penalty: "每天课时分布不均的惩罚力度，越大越均匀",
  room_day_load_penalty: "同一教室单日过度使用的惩罚",
  room_week_load_penalty: "同一教室整周过度使用的惩罚",
  task_day_load_penalty: "同一教学任务集中在同一天的惩罚",
  early_period_penalty: "安排在早课（第1-2节）的惩罚，强避免可拉高到 0.1+",
  late_period_penalty: "安排在晚课（第4-5节）的惩罚，强避免可拉高到 0.08+",
  teacher_profile_penalty_scale: "教师画像软偏好的整体影响强度",
  distribution_penalty_scale: "课表分布均衡的整体影响强度",
  classroom_stickiness_weight: "同一教学任务尽量固定教室，也会偏好原绑定教室",
  compact_bonus_weight: "压缩在更少天数完成的奖励",
  random_jitter: "随机扰动，打破重复模式的微小噪声",
  classroom_stickiness_bonus: "同一教学任务保持在同教室的奖励，越大越不换教室",
  weekend_penalty:
    "仅在允许周末排课时生效；当前生成链路默认硬过滤周六/周日，调这个不是强制开关",
};

const weightMax = {
  teacherProfilePenaltyScale: 100,
  distributionPenaltyScale: 20,
  classroomStickinessWeight: 20,
  compactBonusWeight: 10,
  weekdayLoadPenalty: 0.05,
  roomDayLoadPenalty: 0.06,
  roomWeekLoadPenalty: 0.03,
  taskDayLoadPenalty: 0.08,
  earlyPeriodPenalty: 0.15,
  latePeriodPenalty: 0.12,
  randomJitter: 0.01,
  classroomStickinessBonus: 0.05,
  weekendPenalty: 0.35,
  teacher_profile_penalty_scale: 100,
  distribution_penalty_scale: 20,
  classroom_stickiness_weight: 20,
  compact_bonus_weight: 10,
  weekday_load_penalty: 0.05,
  room_day_load_penalty: 0.06,
  room_week_load_penalty: 0.03,
  task_day_load_penalty: 0.08,
  early_period_penalty: 0.15,
  late_period_penalty: 0.12,
  random_jitter: 0.01,
  classroom_stickiness_bonus: 0.05,
  weekend_penalty: 0.35,
};

// === 任务编辑弹窗新变量 ===
const llmRequirement = ref("");
const llmTranslating = ref(false);
const llmWeightsApplied = ref(false);
const llmInterpretation = ref("");

// 删除旧变量（策略弹窗相关）
const policyDialogVisible = ref(false);
const pendingTaskId = ref(null);
const customRequirement = ref("");
const translating = ref(false);
const customWeights = ref(null);
const editableWeights = ref({ ...PRESET_WEIGHTS.BALANCED });
const policyMode = ref("preset"); // 'preset' | 'custom'
const activePolicy = ref("BALANCED");

const teachingTasks = ref([]);

function csvToNumberArray(value, fallback) {
  if (!value) return [...fallback];
  return String(value)
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
}

function numberArrayToCsv(value) {
  return [...(value || [])].sort((a, b) => a - b).join(",");
}

function normalizeGenerationConfig(rawConfig = {}) {
  const defaults = defaultGenerationConfig();
  return {
    ...defaults,
    ...rawConfig,
    allowedWeeks: csvToNumberArray(
      rawConfig.allowedWeeks,
      defaults.allowedWeeks,
    ),
    allowedWeekdays: csvToNumberArray(
      rawConfig.allowedWeekdays,
      defaults.allowedWeekdays,
    ),
    allowedPeriods: csvToNumberArray(
      rawConfig.allowedPeriods,
      defaults.allowedPeriods,
    ),
  };
}

function serializeGenerationConfig(config) {
  return {
    ...config,
    allowedWeeks: numberArrayToCsv(config.allowedWeeks),
    allowedWeekdays: numberArrayToCsv(config.allowedWeekdays),
    allowedPeriods: numberArrayToCsv(config.allowedPeriods),
  };
}

function presetToGenerationConfigWeights(preset) {
  const weights = PRESET_WEIGHTS[preset] || PRESET_WEIGHTS.BALANCED;
  return {
    weekdayLoadPenalty: weights.weekday_load_penalty,
    roomDayLoadPenalty: weights.room_day_load_penalty,
    roomWeekLoadPenalty: weights.room_week_load_penalty,
    taskDayLoadPenalty: weights.task_day_load_penalty,
    earlyPeriodPenalty: weights.early_period_penalty,
    latePeriodPenalty: weights.late_period_penalty,
    compactBonusWeight: weights.compact_bonus_weight,
    randomJitter: weights.random_jitter,
    classroomStickinessBonus: weights.classroom_stickiness_bonus,
    weekendPenalty: weights.weekend_penalty,
  };
}

function applyPresetToTaskConfig(preset) {
  if (preset === "CUSTOM") return;
  const config = taskForm.value.generationConfig;
  taskForm.value.generationConfig = {
    ...config,
    ...presetToGenerationConfigWeights(preset),
  };
}

function detectWeightsPreset(config) {
  for (const preset of [
    "BALANCED",
    "TEACHER_FRIENDLY",
    "CLASS_BALANCED",
    "ROOM_EFFICIENT",
    "COMPACT",
  ]) {
    const weights = presetToGenerationConfigWeights(preset);
    let matches = true;
    for (const key of Object.keys(weights)) {
      if (Math.abs(config[key] - weights[key]) > 0.0001) {
        matches = false;
        break;
      }
    }
    if (matches) return preset;
  }
  return "CUSTOM";
}

function resetLlmWeights() {
  llmWeightsApplied.value = false;
  llmInterpretation.value = "";
  llmRequirement.value = "";
  taskPolicyPreset.value = "BALANCED";
  applyPresetToTaskConfig("BALANCED");
}

function onWeightChange() {
  taskPolicyPreset.value = "CUSTOM";
  llmWeightsApplied.value = false;
}

async function applyLlmWeights() {
  if (!llmRequirement.value.trim()) {
    ElMessage.warning("请输入排课需求描述");
    return;
  }
  if (
    /(老师|教师|同学|学生|班|课程|[\u4e00-\u9fa5]{2,4}(老师|教师))/.test(
      llmRequirement.value,
    )
  ) {
    ElMessage.warning(
      "全局权重只处理整体偏好；某位教师/班级/课程的特殊要求请维护到教师画像或基础数据中",
    );
    return;
  }
  llmTranslating.value = true;
  try {
    const result = await request.post("/api/param/translate", {
      policyType: "BALANCED",
      extraRequirement: llmRequirement.value.trim(),
    });
    if (result && result.policyParams) {
      const params = result.policyParams;
      const config = taskForm.value.generationConfig;
      taskForm.value.generationConfig = {
        ...config,
        weekdayLoadPenalty:
          params.weekday_load_penalty ?? config.weekdayLoadPenalty,
        roomDayLoadPenalty:
          params.room_day_load_penalty ?? config.roomDayLoadPenalty,
        roomWeekLoadPenalty:
          params.room_week_load_penalty ?? config.roomWeekLoadPenalty,
        taskDayLoadPenalty:
          params.task_day_load_penalty ?? config.taskDayLoadPenalty,
        earlyPeriodPenalty:
          params.early_period_penalty ?? config.earlyPeriodPenalty,
        latePeriodPenalty:
          params.late_period_penalty ?? config.latePeriodPenalty,
        compactBonusWeight:
          params.compact_bonus_weight ?? config.compactBonusWeight,
        randomJitter: params.random_jitter ?? config.randomJitter,
        classroomStickinessBonus:
          params.classroom_stickiness_bonus ?? config.classroomStickinessBonus,
        weekendPenalty: params.weekend_penalty ?? config.weekendPenalty,
      };
      llmWeightsApplied.value = true;
      taskPolicyPreset.value = "CUSTOM";
      llmInterpretation.value = result.interpretation || "";
      ElMessage.success("LLM 已生成策略权重并应用到生成配置");
    } else {
      ElMessage.error("LLM 未返回有效权重");
    }
  } catch (e) {
    ElMessage.error("策略翻译失败: " + (e.message || "未知错误"));
  } finally {
    llmTranslating.value = false;
  }
}

const generationWeightFields = [
  ["teacherProfilePenaltyScale", "教师画像权重"],
  ["distributionPenaltyScale", "分布均衡权重"],
  ["classroomStickinessWeight", "教室粘性权重"],
  ["compactBonusWeight", "紧凑奖励权重"],
  ["weekdayLoadPenalty", "星期均衡惩罚"],
  ["roomDayLoadPenalty", "教室日负载"],
  ["roomWeekLoadPenalty", "教室周负载"],
  ["taskDayLoadPenalty", "单日集中惩罚"],
  ["earlyPeriodPenalty", "早课惩罚"],
  ["latePeriodPenalty", "晚课惩罚"],
  ["randomJitter", "随机扰动"],
  ["classroomStickinessBonus", "教室粘性奖励"],
  ["weekendPenalty", "周末惩罚"],
];

const taskPolicyPreset = ref("BALANCED");

async function loadTasks() {
  tasks.value = await request.get("/api/allocation-tasks");
  restoreRunningGeneration();
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
      generationConfig: normalizeGenerationConfig(row.generationConfig),
    };
    taskPolicyPreset.value = detectWeightsPreset(
      normalizeGenerationConfig(row.generationConfig),
    );
  } else {
    taskForm.value = {
      id: null,
      name: "",
      description: "",
      startWeek: 1,
      endWeek: 18,
      teachingTaskIds: [],
      generationConfig: defaultGenerationConfig(),
    };
    taskPolicyPreset.value = "BALANCED";
  }
  llmRequirement.value = "";
  llmWeightsApplied.value = false;
  llmInterpretation.value = "";
  taskDialog.value = true;
  // 对话框渲染后恢复表格勾选状态
  nextTick(() => {
    if (!taskTableRef.value) return;
    taskTableRef.value.clearSelection();
    const selectedIds = taskForm.value.teachingTaskIds;
    teachingTasks.value.forEach((tt) => {
      if (selectedIds.includes(tt.id)) {
        taskTableRef.value.toggleRowSelection(tt, true);
      }
    });
  });
}

const taskTableRef = ref();

function handleTaskSelectionChange(selection) {
  taskForm.value.teachingTaskIds = selection.map((tt) => tt.id);
}

function selectAllTasks() {
  taskForm.value.teachingTaskIds = teachingTasks.value.map((tt) => tt.id);
  // 同步表格勾选状态
  if (taskTableRef.value) {
    teachingTasks.value.forEach((tt) =>
      taskTableRef.value.toggleRowSelection(tt, true),
    );
  }
}

function clearAllTasks() {
  taskForm.value.teachingTaskIds = [];
  if (taskTableRef.value) {
    taskTableRef.value.clearSelection();
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
  const payload = {
    ...taskForm.value,
    generationConfig: serializeGenerationConfig(
      taskForm.value.generationConfig,
    ),
  };
  if (payload.id) {
    await request.put(`/api/allocation-tasks/${payload.id}`, payload);
  } else {
    await request.post("/api/allocation-tasks", payload);
  }
  ElMessage.success("保存成功");
  taskDialog.value = false;
  loadTasks();
}

async function deleteTask(row) {
  await ElMessageBox.confirm(
    `确认删除分课任务「${row.name}」？相关候选方案、排课明细、正式课表、反馈数据、调整日志和冲突记录都会一起删除。`,
    "删除分课任务",
    { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
  );
  await request.delete(`/api/allocation-tasks/${row.id}`);
  ElMessage.success("删除成功");
  if (currentTaskId.value === row.id) {
    currentTaskId.value = null;
    schemes.value = [];
    schemeVisible.value = false;
    detailVisible.value = false;
  }
  loadTasks();
}

async function viewSchemes(taskId) {
  currentTaskId.value = taskId;
  schemes.value = await request.get(`/api/allocation-tasks/${taskId}/schemes`);
  schemeVisible.value = true;
}

function openGenerateConfirm(row) {
  generateTargetTask.value = row;
  generateConfirmVisible.value = true;
}

async function confirmGenerateTask() {
  const row = generateTargetTask.value;
  if (!row) return;
  generateConfirmVisible.value = false;
  await generateSchemes(row.id);
}

async function generateSchemes(taskId) {
  stopGenerationListeners();
  generating.value = true;
  genProgress.value = 10;
  genStatus.value = {
    stage: "running",
    status: "RUNNING",
    message: "开始生成...",
  };
  currentTaskId.value = taskId;

  try {
    await request.post(`/api/allocation-tasks/${taskId}/generate-async`);
    startSse(taskId);
    loadTasks();
  } catch (e) {
    generating.value = false;
    genStatus.value = { stage: "error", status: "FAILED", message: e.message };
    ElMessage.error("启动生成失败");
  }
}

// === 策略弹窗 ===
function resetEditableWeights(weights) {
  editableWeights.value = { ...(weights || PRESET_WEIGHTS.BALANCED) };
}

function markWeightsCustom() {
  customWeights.value = { ...editableWeights.value };
  policyMode.value = "custom";
}

function openPolicyDialog(taskId) {
  pendingTaskId.value = taskId;
  activePolicy.value = policy.value;
  policyMode.value = customWeights.value ? "custom" : "preset";
  customRequirement.value = "";
  resetEditableWeights(
    customWeights.value || PRESET_WEIGHTS[activePolicy.value],
  );
  policyDialogVisible.value = true;
}

function selectPreset(preset) {
  activePolicy.value = preset;
  policyMode.value = "preset";
  customWeights.value = null;
  resetEditableWeights(PRESET_WEIGHTS[preset]);
}

function containsIndividualPolicyRequirement(text) {
  return /(老师|教师|同学|学生|班|课程|[\u4e00-\u9fa5]{2,4}(老师|教师))/.test(
    text || "",
  );
}

async function translatePolicy() {
  if (!customRequirement.value.trim()) {
    ElMessage.warning("请输入排课需求描述");
    return;
  }
  if (containsIndividualPolicyRequirement(customRequirement.value)) {
    ElMessage.warning(
      "全局权重只处理整体偏好；某位教师/班级/课程的特殊要求请维护到教师画像或基础数据中",
    );
    return;
  }
  translating.value = true;
  try {
    const result = await request.post("/api/param/translate", {
      policyType: activePolicy.value,
      extraRequirement: customRequirement.value.trim(),
    });
    if (result && result.policyParams) {
      customWeights.value = result.policyParams;
      resetEditableWeights(result.policyParams);
      policyMode.value = "custom";
      ElMessage.success("LLM 已生成策略权重");
      if (result.interpretation) {
        ElMessage.info(result.interpretation);
      }
    } else {
      ElMessage.error("LLM 未返回有效权重");
    }
  } catch (e) {
    ElMessage.error("策略翻译失败: " + (e.message || "未知错误"));
  } finally {
    translating.value = false;
  }
}

function resetToPreset() {
  policyMode.value = "preset";
  customWeights.value = null;
  customRequirement.value = "";
  resetEditableWeights(PRESET_WEIGHTS[activePolicy.value]);
}

function displayedWeights() {
  return editableWeights.value;
}

function safeJsonParse(value) {
  if (!value) return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function confirmGenerate() {
  policy.value = activePolicy.value;
  customWeights.value =
    policyMode.value === "custom" ? { ...editableWeights.value } : null;
  policyDialogVisible.value = false;
  generateSchemes(pendingTaskId.value);
}

function stageLabel(stage) {
  const labels = {
    ml: "调用自训练模型...",
    eval: "评估方案质量...",
    rag: "检索画像...",
    prompt: "构建 Prompt...",
    llm: "等待模型...",
    parse: "解析结果...",
    persist: "保存方案...",
    conflict: "检测冲突...",
    running: "生成中...",
    done: "生成完成",
    error: "生成失败",
  };
  return labels[stage] || "生成中...";
}

function isRunningGeneration(status) {
  return status?.status === "RUNNING";
}

function isGeneratingTask(taskId) {
  return generating.value && currentTaskId.value === taskId;
}

async function restoreRunningGeneration() {
  if (generating.value || !tasks.value.length) return;
  for (const task of tasks.value) {
    try {
      const status = await request.get(
        `/api/allocation-tasks/${task.id}/generation-status`,
      );
      if (!isRunningGeneration(status)) continue;
      currentTaskId.value = task.id;
      generating.value = true;
      applyGenerationStatus(task.id, status);
      startSse(task.id);
      return;
    } catch {
      // 单个任务状态恢复失败不影响列表展示
    }
  }
}

function applyGenerationStatus(taskId, status) {
  const isCompleted = status.status === "COMPLETED";
  const isFailed = status.status === "FAILED";
  const stage = isCompleted
    ? "done"
    : isFailed
      ? "error"
      : status.stage || "running";
  genProgress.value = Number.isFinite(status.progress)
    ? status.progress
    : isCompleted || isFailed
      ? 100
      : 50;
  genStatus.value = {
    ...status,
    stage,
    message: isCompleted
      ? `生成完成，共 ${status.schemeCount || 0} 个方案`
      : isFailed
        ? `生成失败: ${status.error || "未知错误"}`
        : status.message || "自训练模型正在生成分课方案...",
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
  generationSource = new EventSource(
    `/api/allocation-tasks/${taskId}/generation-stream`,
  );
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
      const status = await request.get(
        `/api/allocation-tasks/${taskId}/generation-status`,
      );
      applyGenerationStatus(taskId, status);
    } catch (e) {
      stopGenerationListeners();
      generating.value = false;
      genStatus.value = {
        stage: "error",
        status: "FAILED",
        message: e.message,
      };
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

const schemeScores = computed(() => {
  if (!schemeDetail.value?.evaluationSummary) return null;
  try {
    return JSON.parse(schemeDetail.value.evaluationSummary);
  } catch {
    return null;
  }
});
const currentWeek = ref(1);
const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const timetableFilters = ref({
  teachers: [],
  classGroups: [],
  teachingTasks: [],
});

const activeFilterTags = computed(() => {
  const tags = [];
  for (const name of timetableFilters.value.teachers) {
    tags.push({ type: "教师", label: name, clear: () => { timetableFilters.value.teachers = timetableFilters.value.teachers.filter((v) => v !== name); } });
  }
  for (const name of timetableFilters.value.classGroups) {
    tags.push({ type: "班级", label: name, clear: () => { timetableFilters.value.classGroups = timetableFilters.value.classGroups.filter((v) => v !== name); } });
  }
  for (const id of timetableFilters.value.teachingTasks) {
    const opt = timetableTeachingTaskOptions.value.find((o) => o.value === id);
    if (opt) tags.push({ type: "课程", label: opt.label, clear: () => { timetableFilters.value.teachingTasks = timetableFilters.value.teachingTasks.filter((v) => v !== id); } });
  }
  return tags;
});

const hasActiveFilter = computed(
  () =>
    timetableFilters.value.teachers.length > 0 ||
    timetableFilters.value.classGroups.length > 0 ||
    timetableFilters.value.teachingTasks.length > 0,
);

const timetableTeacherOptions = computed(() => {
  const seen = new Set();
  for (const item of schemeDetail.value?.items || []) {
    const name = item.teacherName;
    if (name && !seen.has(name)) seen.add(name);
  }
  return [...seen].sort((a, b) => a.localeCompare(b, "zh-Hans-CN")).map((name) => ({ value: name, label: name }));
});

const timetableClassGroupOptions = computed(() => {
  const names = new Set();
  for (const item of schemeDetail.value?.items || []) {
    String(item.classGroupName || "")
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean)
      .forEach((name) => names.add(name));
  }
  return [...names].sort();
});

const timetableTeachingTaskOptions = computed(() =>
  uniqueOptions(
    schemeDetail.value?.items || [],
    "teachingTaskId",
    "courseName",
  ),
);

const weekItems = computed(() => {
  if (!schemeDetail.value?.items) return [];
  return schemeDetail.value.items.filter(
    (item) =>
      item.weekNumber === currentWeek.value && matchTimetableFilters(item),
  );
});

function uniqueOptions(items, valueKey, labelKey) {
  const map = new Map();
  for (const item of items) {
    const value = item[valueKey];
    if (value == null || map.has(value)) continue;
    map.set(value, item[labelKey] || String(value));
  }
  return [...map.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) =>
      String(a.label).localeCompare(String(b.label), "zh-Hans-CN"),
    );
}

function matchTimetableFilters(item) {
  const filters = timetableFilters.value;
  if (filters.teachers.length > 0 && !filters.teachers.includes(item.teacherName)) return false;
  if (filters.teachingTasks.length > 0 && !filters.teachingTasks.includes(item.teachingTaskId)) return false;
  if (filters.classGroups.length > 0) {
    const itemGroups = String(item.classGroupName || "").split(",").map((g) => g.trim()).filter(Boolean);
    if (!filters.classGroups.some((g) => itemGroups.includes(g))) return false;
  }
  return true;
}

function resetTimetableFilters() {
  timetableFilters.value = { teachers: [], classGroups: [], teachingTasks: [] };
}

function itemHasConflict(item) {
  return item.valid === false;
}

function itemHasProfileExplanation(item) {
  return item.valid !== false && !!item.conflictMessage;
}

function itemsAtSlot(dayOfWeek, periodIndex) {
  return weekItems.value.filter(
    (item) => item.dayOfWeek === dayOfWeek && item.periodIndex === periodIndex,
  );
}

const slotDetail = ref({
  visible: false,
  items: [],
  dayOfWeek: null,
  periodIndex: null,
});

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
  classrooms.value = await request.get(
    `/api/classrooms?status=${ActiveStatus.ACTIVE}`,
  );
}

async function loadTimeSlots() {
  timeSlots.value = await request.get("/api/time-slots");
}

function openEditDialog(item) {
  editingItem.value = { ...item };
  editDialog.value = true;
  loadClassrooms();
  loadTimeSlots();
}

function timeSlotLabel(ts) {
  return `第${ts.weekNumber}周 周${["一", "二", "三", "四", "五", "六", "日"][ts.dayOfWeek - 1]} 第${ts.periodIndex}节`;
}

async function saveItemMove() {
  const item = editingItem.value;
  if (!item.classroomId || !item.timeSlotId) {
    ElMessage.warning("请选择教室和时间段");
    return;
  }
  savingMove.value = true;
  try {
    await request.put(
      `/api/allocation-schemes/${schemeDetail.value.id}/items/${item.id}`,
      {
        classroomId: item.classroomId,
        timeSlotId: item.timeSlotId,
      },
    );
    ElMessage.success("修改成功，已记录调整并重新检测冲突");
    editDialog.value = false;
    // 刷新 schemeDetail 完整数据（含 conflictSummary）+ items
    const [detail, items] = await Promise.all([
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}`),
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}/items`),
    ]);
    schemeDetail.value = { ...schemeDetail.value, ...detail, items };
    // 同步刷新 slot 详情弹窗
    const dayIndex =
      ["周一", "周二", "周三", "周四", "周五", "周六", "周日"].indexOf(
        slotDetail.value.dayOfWeek,
      ) + 1;
    if (dayIndex > 0 && slotDetail.value.periodIndex != null) {
      slotDetail.value = {
        ...slotDetail.value,
        items: items.filter(
          (i) =>
            i.weekNumber === currentWeek.value &&
            i.dayOfWeek === dayIndex &&
            i.periodIndex === slotDetail.value.periodIndex,
        ),
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
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", String(item.id));
}

function onDragOver(e, day, period) {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
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
    ElMessage.warning("该时间段不存在");
    return;
  }
  if (targetTimeSlotId === item.timeSlotId) {
    dragItem.value = null;
    return; // 没变化
  }

  // 调 API
  savingMove.value = true;
  try {
    await request.put(
      `/api/allocation-schemes/${schemeDetail.value.id}/items/${item.id}`,
      {
        classroomId: item.classroomId,
        timeSlotId: targetTimeSlotId,
      },
    );
    ElMessage.success("已移动，调整日志已记录");
    // 刷新 scheme 完整数据（含 conflictSummary）+ items
    const [detail, items] = await Promise.all([
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}`),
      request.get(`/api/allocation-schemes/${schemeDetail.value.id}/items`),
    ]);
    schemeDetail.value = { ...schemeDetail.value, ...detail, items };
  } catch (e) {
    ElMessage.error("移动失败");
  } finally {
    savingMove.value = false;
    dragItem.value = null;
  }
}

async function viewSchemeDetail(schemeId) {
  const [detail, items, allTimeSlots] = await Promise.all([
    request.get(`/api/allocation-schemes/${schemeId}`),
    request.get(`/api/allocation-schemes/${schemeId}/items`),
    request.get("/api/time-slots"),
  ]);
  // 从任务列表中找到对应任务的周次范围
  const task = tasks.value.find((t) => t.id === detail.taskId);
  buildTimeSlotMap(allTimeSlots);
  schemeDetail.value = {
    ...detail,
    items,
    taskStartWeek: task?.startWeek || 1,
    taskEndWeek: task?.endWeek || 18,
  };
  currentWeek.value = task?.startWeek || 1;
  resetTimetableFilters();
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
      <div v-if="generating" style="flex: 1; max-width: 300px">
        <el-progress
          :percentage="genProgress"
          :status="genStatus?.stage === 'error' ? 'exception' : undefined"
          :text-inside="true"
          :stroke-width="20"
        >
          <span>{{ genStatus?.message || "" }}</span>
        </el-progress>
      </div>
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
      <el-table-column label="操作" width="340">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openTaskDialog(row)"
            >编辑</el-button
          >
          <el-button
            type="success"
            size="small"
            :disabled="generating"
            @click="openGenerateConfirm(row)"
          >
            {{
              isGeneratingTask(row.id)
                ? genStatus?.stage
                  ? stageLabel(genStatus.stage)
                  : "生成中..."
                : "生成方案"
            }}
          </el-button>
          <el-button type="info" size="small" @click="viewSchemes(row.id)"
            >查看方案</el-button
          >
          <el-button
            type="danger"
            size="small"
            :disabled="generating"
            @click="deleteTask(row)"
            >删除</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="generateConfirmVisible"
      title="确认生成方案"
      width="460px"
      :close-on-click-modal="false"
    >
      <div v-if="generateTargetTask">
        <p style="margin-top: 0">
          即将为任务「{{ generateTargetTask.name }}」生成候选排课方案。
        </p>
        <el-alert
          type="warning"
          show-icon
          :closable="false"
          title="生成过程可能耗时较久，开始后请不要重复点击生成。"
          style="margin-bottom: 16px"
        />
        <div style="color: #606266; font-size: 13px">
          本次将按任务配置表中的生成方案数执行：
          <strong>{{
            normalizeGenerationConfig(generateTargetTask.generationConfig)
              .schemeCount
          }}</strong>
          个。 如需调整，请先编辑任务的生成配置。
        </div>
      </div>
      <template #footer>
        <el-button @click="generateConfirmVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="generating"
          @click="confirmGenerateTask"
        >
          确认生成
        </el-button>
      </template>
    </el-dialog>

    <!-- Policy Dialog -->
    <el-dialog
      v-model="policyDialogVisible"
      title="选择排课策略"
      width="680px"
      :close-on-click-modal="false"
    >
      <div style="margin-bottom: 16px">
        <div style="font-weight: 600; margin-bottom: 10px; color: #303133">
          生成方案个数
        </div>
        <el-input-number
          v-model="schemeCount"
          :min="1"
          :max="20"
          size="small"
          style="width: 140px"
        />
        <span style="margin-left: 8px; color: #909399; font-size: 12px"
          >一次生成多个候选方案，方便横向比较</span
        >
      </div>

      <!-- 预设选择 -->
      <div style="margin-bottom: 16px">
        <div style="font-weight: 600; margin-bottom: 10px; color: #303133">
          预设策略
        </div>
        <el-radio-group
          v-model="activePolicy"
          @change="selectPreset"
          style="display: flex; flex-wrap: wrap; gap: 8px"
        >
          <el-radio-button
            v-for="opt in policyOptions"
            :key="opt.value"
            :value="opt.value"
            :disabled="translating"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
        <div style="margin-top: 6px; font-size: 12px; color: #909399">
          {{ policyOptions.find((o) => o.value === activePolicy)?.desc || "" }}
        </div>
      </div>

      <!-- LLM 翻译 -->
      <el-divider content-position="left">LLM 自定义权重</el-divider>
      <div style="display: flex; gap: 8px; margin-bottom: 8px">
        <el-input
          v-model="customRequirement"
          placeholder="如：减少上午排课、尽量不排周末、课表更紧凑"
          :disabled="translating"
          style="flex: 1"
          @keyup.enter="translatePolicy"
        />
        <el-button
          type="primary"
          :loading="translating"
          @click="translatePolicy"
        >
          翻译
        </el-button>
      </div>
      <div style="font-size: 12px; color: #909399; margin: -2px 0 12px">
        这里只调整全局排课风格；某位教师的特殊时间、工作量或偏好请到教师画像中维护。
      </div>
      <div
        v-if="policyMode === 'custom'"
        style="
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
        "
      >
        <el-tag type="warning" size="small">LLM 自定义权重</el-tag>
        <el-button size="small" text @click="resetToPreset">恢复预设</el-button>
      </div>

      <!-- 权重展示 -->
      <div style="background: #f8fafc; border-radius: 8px; padding: 14px 16px">
        <div
          style="
            font-weight: 600;
            font-size: 13px;
            color: #303133;
            margin-bottom: 10px;
          "
        >
          {{
            policyMode === "custom"
              ? "当前权重（自定义）"
              : "当前权重（预设，可手动调整）"
          }}
        </div>
        <div
          style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px"
        >
          <div
            v-for="(val, key) in displayedWeights()"
            :key="key"
            :title="weightDescs[key] || key"
            style="
              display: flex;
              justify-content: space-between;
              align-items: center;
              gap: 8px;
              padding: 5px 8px;
              border-radius: 6px;
              background: #fff;
              font-size: 12px;
            "
          >
            <span style="color: #606266">{{ weightLabels[key] || key }}</span>
            <el-input-number
              v-model="editableWeights[key]"
              :min="0"
              :max="weightMax[key] || 1"
              :step="0.001"
              :precision="3"
              controls-position="right"
              size="small"
              style="width: 116px"
              @change="markWeightsCustom"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="policyDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="confirmGenerate"
          :disabled="translating"
        >
          确认生成
        </el-button>
      </template>
    </el-dialog>

    <!-- Task Dialog -->
    <el-dialog
      v-model="taskDialog"
      :title="taskForm.id ? '编辑任务' : '新建任务'"
      width="960px"
    >
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="taskForm.name" />
        </el-form-item>
        <el-divider content-position="left">生成配置</el-divider>
        <el-form-item label="生成方案数">
          <el-input-number
            v-model="taskForm.generationConfig.schemeCount"
            :min="1"
            :max="5"
          />
          <span style="margin-left: 8px; color: #909399; font-size: 12px"
            >点击生成时按这里的数量生成候选方案</span
          >
        </el-form-item>
        <el-form-item label="周次多选">
          <el-checkbox-group
            v-model="taskForm.generationConfig.allowedWeeks"
            style="display: flex; flex-wrap: wrap; gap: 4px 10px"
          >
            <el-checkbox
              v-for="week in weekOptions"
              :key="week"
              :value="week"
              >{{ week }}</el-checkbox
            >
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="星期多选">
          <el-checkbox-group
            v-model="taskForm.generationConfig.allowedWeekdays"
          >
            <el-checkbox
              v-for="day in weekdayOptions"
              :key="day.value"
              :value="day.value"
              >{{ day.label }}</el-checkbox
            >
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="节次多选">
          <el-checkbox-group v-model="taskForm.generationConfig.allowedPeriods">
            <el-checkbox
              v-for="period in periodOptions"
              :key="period.value"
              :value="period.value"
              >{{ period.label }}</el-checkbox
            >
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="策略预设">
          <el-radio-group
            v-model="taskPolicyPreset"
            @change="applyPresetToTaskConfig"
          >
            <el-radio-button
              v-for="opt in policyOptions"
              :key="opt.value"
              :value="opt.value"
              >{{ opt.label }}</el-radio-button
            >
          </el-radio-group>
        </el-form-item>
        <el-form-item label="LLM 权重">
          <div style="display: flex; gap: 8px; margin-bottom: 8px; width: 100%">
            <el-input
              v-model="llmRequirement"
              placeholder="如：减少上午排课、尽量不排周末、课表更紧凑"
              style="flex: 1"
              size="small"
            />
            <el-button
              type="primary"
              size="small"
              :loading="llmTranslating"
              @click="applyLlmWeights"
            >
              LLM 翻译
            </el-button>
          </div>
          <div
            v-if="llmInterpretation"
            style="
              margin: 4px 0 8px;
              padding: 8px 12px;
              background: #f0f9ff;
              border-radius: 6px;
              font-size: 12px;
              color: #606266;
              line-height: 1.6;
            "
          >
            {{ llmInterpretation }}
          </div>
          <div
            v-if="llmWeightsApplied"
            style="display: flex; align-items: center; gap: 8px"
          >
            <el-tag type="warning" size="small">LLM 自定义权重</el-tag>
            <el-button size="small" text @click="resetLlmWeights">
              恢复预设
            </el-button>
          </div>
          <div style="font-size: 12px; color: #909399; margin: 2px 0 0">
            这里只调整全局排课风格；某位教师的特殊时间、工作量或偏好请到教师画像中维护。
          </div>
        </el-form-item>
        <el-form-item label="软权重">
          <div
            style="
              display: grid;
              grid-template-columns: repeat(2, minmax(240px, 1fr));
              gap: 8px;
              width: 100%;
            "
          >
            <div
              v-for="[key, label] in generationWeightFields"
              :key="key"
              :title="weightDescs[key] || key"
              style="
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                padding: 6px 8px;
                border: 1px solid #ebeef5;
                border-radius: 6px;
              "
            >
              <span style="font-size: 12px; color: #606266">{{ label }}</span>
              <el-input-number
                v-model="taskForm.generationConfig[key]"
                :min="0"
                :max="weightMax[key] || 100"
                :step="
                  key.toLowerCase().includes('scale') || key.includes('Weight')
                    ? 1
                    : 0.001
                "
                :precision="
                  key.toLowerCase().includes('scale') || key.includes('Weight')
                    ? 2
                    : 3
                "
                size="small"
                controls-position="right"
                style="width: 120px"
                @change="onWeightChange"
              />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="教学任务">
          <div
            style="
              margin-bottom: 8px;
              display: flex;
              gap: 8px;
              align-items: center;
            "
          >
            <el-button size="small" @click="selectAllTasks">全选</el-button>
            <el-button size="small" @click="clearAllTasks">清空</el-button>
            <span style="font-size: 12px; color: #909399">
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
            <el-table-column
              prop="primaryTeacher.name"
              label="教师"
              width="80"
            />
            <el-table-column label="班级" width="150">
              <template #default="{ row }">
                {{ row.classGroups?.map((cg) => cg.name).join(", ") || "-" }}
              </template>
            </el-table-column>
            <el-table-column prop="totalHours" label="课时" width="60" />
            <el-table-column label="教室" width="100">
              <template #default="{ row }">
                {{ row.classroom?.name || "-" }}
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
            <span
              v-if="row.schemeScore != null"
              style="font-weight: 700; color: #67c23a"
            >
              {{ row.schemeScore.toFixed(1) }}
            </span>
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
              >{{
                row.status === SchemeStatus.CONFIRMED ? "重新确认" : "确认"
              }}</el-button
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
            <el-tag
              v-if="schemeDetail.conflictSummary"
              type="danger"
              size="small"
              >冲突: {{ schemeDetail.conflictSummary }}</el-tag
            >
          </div>
        </div>

        <!-- 周次分页 & 筛选 -->
        <div
          style="
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
          "
        >
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
            （当前视图 {{ weekItems.length }} 个排课片段）
          </span>
          <div style="flex: 1"></div>
          <div style="display: flex; align-items: center; gap: 6px; background: #f8fafc; padding: 4px 10px 4px 16px; border-radius: 6px; font-size: 12px; color: #909399">
            <span>筛选</span>
            <el-tag v-for="tag in activeFilterTags" :key="tag.type + tag.label" size="small" closable @close="tag.clear()">{{ tag.type }}: {{ tag.label }}</el-tag>
            <el-button v-if="hasActiveFilter" size="small" text @click="resetTimetableFilters" style="font-size: 12px">× 清除</el-button>
          </div>
          <el-select
            v-model="timetableFilters.teachers"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            filterable
            size="small"
            placeholder="教师"
            style="width: 130px"
          >
            <el-option
              v-for="teacher in timetableTeacherOptions"
              :key="teacher.value"
              :label="teacher.label"
              :value="teacher.value"
            />
          </el-select>
          <el-select
            v-model="timetableFilters.classGroups"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            filterable
            size="small"
            placeholder="班级"
            style="width: 130px"
          >
            <el-option
              v-for="name in timetableClassGroupOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
          <el-select
            v-model="timetableFilters.teachingTasks"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            filterable
            size="small"
            placeholder="课程"
            style="width: 130px"
          >
            <el-option
              v-for="task in timetableTeachingTaskOptions"
              :key="task.value"
              :label="task.label"
              :value="task.value"
            />
          </el-select>
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
                  <div
                    v-if="itemsAtSlot(day, period).length > 0"
                    style="display: flex; flex-direction: column; gap: 3px"
                  >
                    <div
                      v-for="item in itemsAtSlot(day, period)"
                      :key="item.id"
                      draggable="true"
                      :style="{
                        padding: '3px 5px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        lineHeight: '1.4',
                        background: itemHasConflict(item)
                          ? 'var(--el-color-danger-light-9, #fef0f0)'
                          : itemHasProfileExplanation(item)
                            ? 'var(--el-color-warning-light-9, #fdf6ec)'
                            : 'var(--el-color-primary-light-9, #ecf5ff)',
                        color: itemHasConflict(item)
                          ? 'var(--el-color-danger, #f56c6c)'
                          : itemHasProfileExplanation(item)
                            ? 'var(--el-color-warning, #e6a23c)'
                            : 'var(--el-color-primary, #409eff)',
                        border: itemHasConflict(item)
                          ? '1px solid var(--el-color-danger-light-5, #fab6b6)'
                          : itemHasProfileExplanation(item)
                            ? '1px solid var(--el-color-warning-light-5, #f3d19e)'
                            : '1px solid transparent',
                        cursor: 'grab',
                      }"
                      @dragstart="onDragStart($event, item)"
                      @click.stop="openEditDialog(item)"
                    >
                      <div style="font-weight: 600">{{ item.courseName }}</div>
                      <div
                        :style="{
                          color: itemHasConflict(item)
                            ? '#c45656'
                            : itemHasProfileExplanation(item)
                              ? '#b88230'
                              : '#666',
                        }"
                      >
                        {{ item.classroomName }} · {{ item.teacherName }}
                      </div>
                      <div style="color: #999; font-size: 11px">
                        {{ item.classGroupName }}
                      </div>
                      <el-tag
                        v-if="itemHasProfileExplanation(item)"
                        type="warning"
                        size="small"
                        effect="plain"
                        >画像扣分</el-tag
                      >
                    </div>
                  </div>
                  <div
                    v-else
                    style="
                      color: #ccc;
                      text-align: center;
                      font-size: 11px;
                      line-height: 40px;
                    "
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
          >{{
            schemeDetail?.status === SchemeStatus.CONFIRMED
              ? "重新确认"
              : "确认方案"
          }}</el-button
        >
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
            <el-tag :type="row.valid ? 'success' : 'danger'" size="small">{{
              row.valid ? "是" : "否"
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          v-if="slotDetail.items.some((i) => i.conflictMessage)"
          label="说明"
          min-width="220"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-tag v-if="itemHasConflict(row)" type="danger" size="small"
              >冲突</el-tag
            >
            <el-tag v-else type="warning" size="small" effect="plain"
              >画像扣分</el-tag
            >
            <span style="margin-left: 6px">{{ row.conflictMessage }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openEditDialog(row)"
              >编辑</el-button
            >
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
        <el-form-item label="教室">
          <el-select
            v-model="editingItem.classroomId"
            filterable
            placeholder="选择教室"
            style="width: 100%"
          >
            <el-option
              v-for="room in classrooms"
              :key="room.id"
              :label="`${room.name || room.classroomName || room.id} · ${room.classroomType || room.type || '普通教室'} · ${room.capacity || 0}人`"
              :value="room.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间段">
          <el-select
            v-model="editingItem.timeSlotId"
            filterable
            placeholder="选择时间段"
            style="width: 100%"
          >
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
        <el-button type="primary" :loading="savingMove" @click="saveItemMove"
          >保存</el-button
        >
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
.dim-card {
  padding: 8px 14px;
  border-radius: 10px;
  text-align: center;
  min-width: 80px;
}
.dim-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.dim-value {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}
.main-score {
  color: #409eff;
}
.timetable td,
.timetable th {
  border-color: var(--el-border-color-light, #dcdfe6);
}
</style>
