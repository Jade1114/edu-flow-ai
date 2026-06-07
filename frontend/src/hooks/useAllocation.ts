import { useState, useEffect } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface AllocationTask { id: number; name: string; generationConfig?: any; schemeCount?: number; status: string; }
interface AllocationScheme { id: number; allocationTaskId: number; name?: string; status: string; createdAt?: string; schemeScore?: number; valid?: boolean; }
interface GenerationStatus { status?: string; stage?: string; message?: string; progress?: number; error?: string; schemeCount?: number; }

export interface SchemeItem {
  id: number;
  schemeId: number;
  teachingTaskId: number;
  courseName: string;
  teacherName: string;
  classGroupName: string;
  classroomId: number;
  classroomName: string;
  timeSlotId: number;
  timeSlotLabel: string;
  weekNumber: number;
  dayOfWeek: number;
  periodIndex: number;
  teacherProfileScore?: number;
  teacherProfilePenalty?: number;
  valid: boolean;
  conflictMessage?: string;
}

interface TeachingTaskBrief {
  id: number;
  courseName: string;
  teacherName: string;
  classGroupNames: string;
}

const WEEKS = Array.from({length: 18}, (_, i) => i + 1);
const WEEKDAYS = [{l:"周一",v:1},{l:"周二",v:2},{l:"周三",v:3},{l:"周四",v:4},{l:"周五",v:5},{l:"周六",v:6},{l:"周日",v:7}];
const PERIODS = [1,2,3,4];

const defaultConfig = () => ({
  allowedWeeks: WEEKS, allowedWeekdays: [1,2,3,4,5], allowedPeriods: PERIODS,
  schemeCount: 3, generationMode: "AUTO", placementTopK: 80, rawPlanCount: 240, cpPlanCount: 80,
  solverTimeLimitSeconds: 3600, teacherProfilePenaltyScale: 80, earlyPeriodPenalty: 0.04, latePeriodPenalty: 0.03,
  weekendPenalty: 0.05, modelWeight: 0.6, llmWeight: 0.4, sameDayWeight: 0.05,
  capacityWastePenalty: 0, teacherDayLoadPenalty: 0, classDayLoadPenalty: 0, teacherOverloadPenalty: 0,
});

export function useAllocation() {
  const [tasks, setTasks] = useState<AllocationTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [taskDialog, setTaskDialog] = useState(false);
  const [taskForm, setTaskForm] = useState({ id: null as number|null, name: "", teachingTaskIds: [] as number[], generationConfig: defaultConfig() });
  const [saving, setSaving] = useState(false);
  const [selectedTask, setSelectedTask] = useState<AllocationTask | null>(null);
  const [schemes, setSchemes] = useState<AllocationScheme[]>([]);
  const [schemesLoading, setSchemesLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateStatus, setGenerateStatus] = useState("");
  const [generateProgress, setGenerateProgress] = useState(0);

  // Scheme detail
  const [detailScheme, setDetailScheme] = useState<AllocationScheme | null>(null);
  const [schemeItems, setSchemeItems] = useState<SchemeItem[]>([]);
  const [schemeItemsLoading, setSchemeItemsLoading] = useState(false);

  // Teaching task briefs (for task dialog selector)
  const [teachingTasks, setTeachingTasks] = useState<TeachingTaskBrief[]>([]);
  const [teachingTasksLoading, setTeachingTasksLoading] = useState(false);

  useEffect(() => { loadTasks(); }, []);

  async function loadTasks() {
    setLoading(true);
    try { setTasks(await request.get("/api/allocation-tasks")); } catch { setTasks([]); }
    finally { setLoading(false); }
  }

  async function loadTeachingTasks() {
    setTeachingTasksLoading(true);
    try {
      const raw: any = await request.get("/api/teaching-tasks");
      const list: any[] = Array.isArray(raw) ? raw : raw?.content ?? [];
      setTeachingTasks(list.map(t => ({
        id: t.id,
        courseName: t.course?.name || `课程#${t.courseId}`,
        teacherName: t.primaryTeacher?.name || "",
        classGroupNames: t.classGroups?.map((cg: any) => cg.name).join(", ") || "",
      })));
    } catch { setTeachingTasks([]); }
    finally { setTeachingTasksLoading(false); }
  }

  function openTaskDialog(row?: AllocationTask) {
    if (row) {
      setTaskForm({ id: row.id, name: row.name, teachingTaskIds: [], generationConfig: row.generationConfig || defaultConfig() });
    } else {
      setTaskForm({ id: null, name: "", teachingTaskIds: [], generationConfig: defaultConfig() });
    }
    loadTeachingTasks();
    setTaskDialog(true);
  }

  async function saveTask() {
    setSaving(true);
    try {
      if (taskForm.id) await request.put(`/api/allocation-tasks/${taskForm.id}`, taskForm);
      else await request.post("/api/allocation-tasks", taskForm);
      toast.success("保存成功");
      setTaskDialog(false);
      loadTasks();
    } catch { toast.error("保存失败"); }
    finally { setSaving(false); }
  }

  async function deleteTask(id: number) {
    if (!confirm("确认删除该排课任务？")) return;
    try { await request.delete(`/api/allocation-tasks/${id}`); toast.success("已删除"); loadTasks(); }
    catch { toast.error("删除失败"); }
  }

  async function selectTask(task: AllocationTask) {
    setSelectedTask(task);
    setDetailScheme(null);
    setSchemeItems([]);
    setSchemesLoading(true);
    try {
      const data = await request.get("/api/allocation-schemes", { params: { taskId: task.id } });
      setSchemes(Array.isArray(data) ? data : data?.content || []);
    } catch { setSchemes([]); }
    finally { setSchemesLoading(false); }
  }

  async function loadSchemeItems(scheme: AllocationScheme) {
    setDetailScheme(scheme);
    setSchemeItemsLoading(true);
    try {
      const data = await request.get(`/api/allocation-schemes/${scheme.id}/items`);
      setSchemeItems(Array.isArray(data) ? data : []);
    } catch { setSchemeItems([]); toast.error("加载方案明细失败"); }
    finally { setSchemeItemsLoading(false); }
  }

  function formatGenerationStatus(status: GenerationStatus) {
    const progress = typeof status.progress === "number" ? `（${status.progress}%）` : "";
    const count = typeof status.schemeCount === "number" ? `，已生成 ${status.schemeCount} 个方案` : "";
    return status.message || status.stage ? `${status.message || status.stage}${progress}${count}` : `排课中...${progress}${count}`;
  }

  async function waitForGenerationStream(taskId: number) {
    const token = localStorage.getItem("edu-flow-token");
    const response = await fetch(`/api/allocation-tasks/${taskId}/generation-stream`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) throw new Error("进度流连接失败");
    if (!response.body) throw new Error("浏览器不支持进度流");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const handleChunk = (chunk: string) => {
      buffer += chunk;
      const messages = buffer.split("\n\n");
      buffer = messages.pop() || "";
      for (const message of messages) {
        const dataLine = message.split("\n").find(line => line.startsWith("data:"));
        if (!dataLine) continue;
        const rawData = dataLine.slice(5).trim();
        if (!rawData) continue;
        const status = JSON.parse(rawData) as GenerationStatus;
        setGenerateStatus(formatGenerationStatus(status));
        if (typeof status.progress === "number") setGenerateProgress(status.progress);
        if (status.status === "COMPLETED") return "COMPLETED";
        if (status.status === "FAILED") throw new Error(status.error || status.message || "排课失败");
      }
      return null;
    };

    while (true) {
      const { done, value } = await reader.read();
      if (value) {
        const result = handleChunk(decoder.decode(value, { stream: !done }));
        if (result === "COMPLETED") return;
      }
      if (done) return;
    }
  }

  async function generateSchemes() {
    if (!selectedTask) return;
    setGenerating(true);
    setGenerateProgress(0);
    setGenerateStatus("提交排课任务...");
    try {
      const initialStatus = await request.post<GenerationStatus>(`/api/allocation-tasks/${selectedTask.id}/generate-async`);
      setGenerateStatus(formatGenerationStatus(initialStatus));
      await waitForGenerationStream(selectedTask.id);
      toast.success("排课完成");
      await selectTask(selectedTask);
    } catch (e: any) { toast.error("排课失败: " + (e.message || "")); }
    finally { setGenerating(false); setGenerateProgress(0); setGenerateStatus(""); }
  }

  async function confirmScheme(schemeId: number) {
    try {
      await request.post(`/api/allocation-schemes/${schemeId}/confirm`);
      toast.success("方案已确认");
      if (selectedTask) selectTask(selectedTask);
    } catch { toast.error("确认失败"); }
  }

  function updateConfig(key: string, value: any) {
    setTaskForm(f => ({ ...f, generationConfig: { ...f.generationConfig, [key]: value } }));
  }

  function toggleTeachingTask(taskId: number) {
    setTaskForm(f => ({
      ...f,
      teachingTaskIds: f.teachingTaskIds.includes(taskId)
        ? f.teachingTaskIds.filter(id => id !== taskId)
        : [...f.teachingTaskIds, taskId],
    }));
  }

  function selectAllTeachingTasks(select: boolean) {
    setTaskForm(f => ({
      ...f,
      teachingTaskIds: select ? teachingTasks.map(t => t.id) : [],
    }));
  }

  const dayNames = ["周日","周一","周二","周三","周四","周五","周六"];

  return {
    tasks, loading, taskDialog, setTaskDialog, taskForm, setTaskForm, saving,
    selectedTask, schemes, schemesLoading, generating, generateStatus, generateProgress,
    WEEKS, WEEKDAYS, PERIODS,
    detailScheme, schemeItems, schemeItemsLoading,
    teachingTasks, teachingTasksLoading,
    loadTasks, openTaskDialog, saveTask, deleteTask, selectTask,
    generateSchemes, confirmScheme, updateConfig,
    loadSchemeItems, toggleTeachingTask, selectAllTeachingTasks,
    dayNames,
  };
}
