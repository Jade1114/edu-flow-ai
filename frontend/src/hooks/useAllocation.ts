import { useState, useEffect } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface AllocationTask { id: number; name: string; generationConfig?: any; schemeCount?: number; status: string; teachingTasks?: { id: number }[]; }
export interface AllocationScheme { id: number; allocationTaskId: number; name?: string; status: string; createdAt?: string; schemeScore?: number; valid?: boolean; }
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
  taskBatch: string;
}

const WEEKS = Array.from({length: 18}, (_, i) => i + 1);
const WEEKDAYS = [{l:"周一",v:1},{l:"周二",v:2},{l:"周三",v:3},{l:"周四",v:4},{l:"周五",v:5},{l:"周六",v:6},{l:"周日",v:7}];
const PERIODS = [1,2,3,4];

const defaultConfig = () => ({
  allowedWeeks: "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18",
  allowedWeekdays: "1,2,3,4,5",
  allowedPeriods: "1,2,3,4",
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
  const [teachingTaskBatchFilter, setTeachingTaskBatchFilter] = useState("");

  // V3.5 template state
  const [v35Templates, setV35Templates] = useState<any[]>([]);
  const [v35TemplateWeeks, setV35TemplateWeeks] = useState<any[]>([]);
  const [v35WeekTimetable, setV35WeekTimetable] = useState<any[]>([]);
  const [v35SelectedWeek, setV35SelectedWeek] = useState<number | null>(null);
  const [v35TemplatesLoading, setV35TemplatesLoading] = useState(false);

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
        taskBatch: t.taskBatch || "DEFAULT",
      })));
    } catch { setTeachingTasks([]); }
    finally { setTeachingTasksLoading(false); }
  }

  const filteredTeachingTasks = !teachingTaskBatchFilter
    ? teachingTasks
    : teachingTasks.filter(tt => tt.taskBatch === teachingTaskBatchFilter);

  const teachingTaskBatchOptions = [...new Set(teachingTasks.map(tt => tt.taskBatch))].sort();

  async function openTaskDialog(row?: AllocationTask) {
    if (row) {
      const teachingTaskIds = row.teachingTasks?.map(tt => tt.id) ?? [];
      setTaskForm({ id: row.id, name: row.name, teachingTaskIds, generationConfig: row.generationConfig || defaultConfig() });
      try {
        const detail: AllocationTask = await request.get(`/api/allocation-tasks/${row.id}`);
        setTaskForm({
          id: detail.id,
          name: detail.name,
          teachingTaskIds: detail.teachingTasks?.map(tt => tt.id) ?? teachingTaskIds,
          generationConfig: detail.generationConfig || row.generationConfig || defaultConfig(),
        });
      } catch {
        // 保留列表行数据，避免编辑入口直接失败
      }
    } else {
      setTaskForm({ id: null, name: "", teachingTaskIds: [], generationConfig: defaultConfig() });
    }
    loadTeachingTasks();
    setTaskDialog(true);
  }

  function serializeConfig(cfg: any) {
    const serialized = { ...cfg };
    if (Array.isArray(serialized.allowedWeeks)) serialized.allowedWeeks = serialized.allowedWeeks.join(",");
    if (Array.isArray(serialized.allowedWeekdays)) serialized.allowedWeekdays = serialized.allowedWeekdays.join(",");
    if (Array.isArray(serialized.allowedPeriods)) serialized.allowedPeriods = serialized.allowedPeriods.join(",");
    return serialized;
  }

  async function saveTask() {
    setSaving(true);
    try {
      const body = {
        ...taskForm,
        generationConfig: taskForm.generationConfig ? serializeConfig(taskForm.generationConfig) : taskForm.generationConfig,
      };
      if (taskForm.id) await request.put(`/api/allocation-tasks/${taskForm.id}`, body);
      else await request.post("/api/allocation-tasks", body);
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

  async function loadV35Templates(taskId: number) {
    setV35TemplatesLoading(true);
    try {
      const templatesData = await request.get(`/api/allocation-tasks/${taskId}/templates`);
      const weeksData = await request.get(`/api/allocation-tasks/${taskId}/templates/weeks`);
      setV35Templates(Array.isArray(templatesData) ? templatesData : []);
      setV35TemplateWeeks(Array.isArray(weeksData) ? weeksData : []);
      setV35WeekTimetable([]);
      setV35SelectedWeek(null);
    } catch {
      setV35Templates([]);
      setV35TemplateWeeks([]);
    } finally {
      setV35TemplatesLoading(false);
    }
  }

  async function loadV35WeekTimetable(taskId: number, weekNumber: number) {
    try {
      const data = await request.get(`/api/allocation-tasks/${taskId}/templates/weeks/${weekNumber}/timetable`);
      setV35WeekTimetable(Array.isArray(data) ? data : []);
      setV35SelectedWeek(weekNumber);
    } catch {
      setV35WeekTimetable([]);
    }
  }

  async function generateSchemes() {
    if (!selectedTask) return;
    setGenerating(true);
    setGenerateProgress(0);
    setGenerateStatus("正在触发 V3.5 模板排课...");
    const taskId = selectedTask.id;
    try {
      await request.post(`/api/allocation-tasks/${taskId}/templates/generate`, {
        importDb: true,
        truncateDb: false,
      });
      setGenerateStatus("V3.5 排课进行中，请稍候...");
      setGenerateProgress(30);

      // Poll generation status (V3.5 doesn't have SSE yet)
      const pollInterval = 3000;
      const maxPolls = 120;
      for (let i = 0; i < maxPolls; i++) {
        await new Promise(r => setTimeout(r, pollInterval));
        try {
          const status: any = await request.get(`/api/allocation-tasks/${taskId}/templates/generation-status`);
          if (status.status === "SUCCESS") {
            setGenerateStatus("排课完成");
            setGenerateProgress(100);
            toast.success("V3.5 模板排课完成");
            await loadV35Templates(taskId);
            // 刷新方案列表，让新创建的 V3.5 方案出现在列表中
            const updatedTask = tasks.find(t => t.id === taskId);
            if (updatedTask) await selectTask(updatedTask);
            return;
          }
          if (status.status === "FAILED") {
            throw new Error(status.error || "V3.5 排课失败");
          }
          if (status.status === "RUNNING") {
            setGenerateProgress(50 + Math.floor(i / 4));
          }
        } catch (pollErr: any) {
          if (pollErr.message?.includes("FAILED")) throw pollErr;
          setGenerateStatus("等待排课服务响应...");
        }
      }
      throw new Error("排课超时");
    } catch (e: any) {
      toast.error("V3.5 排课失败: " + (e.message || ""));
    } finally {
      setGenerating(false);
      setGenerateProgress(0);
      setGenerateStatus("");
    }
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
    const source = teachingTaskBatchFilter ? filteredTeachingTasks : teachingTasks;
    setTaskForm(f => ({
      ...f,
      teachingTaskIds: select
        ? [...new Set([...f.teachingTaskIds, ...source.map(t => t.id)])]
        : f.teachingTaskIds.filter(id => !source.some(t => t.id === id)),
    }));
  }

  const dayNames = ["周日","周一","周二","周三","周四","周五","周六"];

  return {
    tasks, loading, taskDialog, setTaskDialog, taskForm, setTaskForm, saving,
    selectedTask, schemes, schemesLoading, generating, generateStatus, generateProgress,
    WEEKS, WEEKDAYS, PERIODS,
    detailScheme, schemeItems, schemeItemsLoading,
    teachingTasks, teachingTasksLoading,
    filteredTeachingTasks, teachingTaskBatchFilter, setTeachingTaskBatchFilter, teachingTaskBatchOptions,
    loadTasks, openTaskDialog, saveTask, deleteTask, selectTask,
    generateSchemes, confirmScheme, updateConfig,
    loadSchemeItems, setDetailScheme, toggleTeachingTask, selectAllTeachingTasks,
    dayNames,
    v35Templates, v35TemplateWeeks, v35WeekTimetable, v35SelectedWeek,
    v35TemplatesLoading, loadV35Templates, loadV35WeekTimetable,
  };
}
