import { useState, useEffect } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface AllocationTask { id: number; name: string; generationConfig?: any; schemeCount?: number; status: string; }
interface AllocationScheme { id: number; allocationTaskId: number; name?: string; status: string; createdAt?: string; }
interface FeedbackEvent { id: number; taskId: number; schemeId: number; eventType: string; }

const WEEKS = Array.from({length: 18}, (_, i) => i + 1);
const WEEKDAYS = [{l:"周一",v:1},{l:"周二",v:2},{l:"周三",v:3},{l:"周四",v:4},{l:"周五",v:5},{l:"周六",v:6},{l:"周日",v:7}];
const PERIODS = [1,2,3,4];

const defaultConfig = () => ({
  allowedWeeks: WEEKS, allowedWeekdays: [1,2,3,4,5], allowedPeriods: PERIODS,
  schemeCount: 3, generationMode: "AUTO", placementTopK: 80, rawPlanCount: 240, cpPlanCount: 80,
  solverTimeLimitSeconds: 1800, teacherProfilePenaltyScale: 80, earlyPeriodPenalty: 0.04, latePeriodPenalty: 0.03,
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

  useEffect(() => { loadTasks(); }, []);

  async function loadTasks() {
    setLoading(true);
    try { setTasks(await request.get("/api/allocation-tasks")); } catch { setTasks([]); }
    finally { setLoading(false); }
  }

  function openTaskDialog(row?: AllocationTask) {
    if (row) setTaskForm({ id: row.id, name: row.name, teachingTaskIds: [], generationConfig: row.generationConfig || defaultConfig() });
    else setTaskForm({ id: null, name: "", teachingTaskIds: [], generationConfig: defaultConfig() });
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
    setSchemesLoading(true);
    try {
      const data = await request.get("/api/allocation-schemes", { params: { taskId: task.id } });
      setSchemes(Array.isArray(data) ? data : data?.content || []);
    } catch { setSchemes([]); }
    finally { setSchemesLoading(false); }
  }

  async function generateSchemes() {
    if (!selectedTask) return;
    setGenerating(true);
    setGenerateStatus("排课中...");
    try {
      await request.post("/api/ml/v3/generate", { allocation_task_id: selectedTask.id });
      toast.success("排课完成");
      selectTask(selectedTask);
    } catch (e: any) { toast.error("排课失败: " + (e.message || "")); }
    finally { setGenerating(false); setGenerateStatus(""); }
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

  return { tasks, loading, taskDialog, setTaskDialog, taskForm, saving, selectedTask, schemes, schemesLoading, generating, generateStatus, WEEKS, WEEKDAYS, PERIODS, loadTasks, openTaskDialog, saveTask, deleteTask, selectTask, generateSchemes, confirmScheme, updateConfig };
}
