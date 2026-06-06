import { useState, useEffect } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface Task { id: number; name?: string; }
interface Constraint { id?: string; type: string; targetType: string; targetId: string; reason: string; enabled?: boolean; }

export function useConstraintEditor() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<any>(null);
  const [inputText, setInputText] = useState("");
  const [translating, setTranslating] = useState(false);
  const [preview, setPreview] = useState<Constraint[]>([]);

  useEffect(() => { loadTasks(); }, []);

  async function loadTasks() {
    setLoading(true);
    try {
      const data = await request.get("/api/allocation-tasks");
      const list = Array.isArray(data) ? data : [];
      setTasks(list);
      if (list.length > 0 && !selectedTaskId) {
        setSelectedTaskId(list[0].id);
        loadConstraints(list[0].id);
      }
    } finally { setLoading(false); }
  }

  async function loadConstraints(taskId?: number) {
    const id = taskId ?? selectedTaskId;
    if (!id) return;
    setLoading(true);
    try {
      const data = await request.get(`/api/allocation-tasks/${id}`);
      const cfg = data?.generationConfig || null;
      setConfig(cfg);
      const raw = cfg?.llmOverrides;
      if (raw) {
        try { setConstraints(typeof raw === "string" ? JSON.parse(raw)?.overrides || [] : raw?.overrides || []); }
        catch { setConstraints([]); }
      } else setConstraints([]);
    } finally { setLoading(false); }
  }

  async function translateInput() {
    if (!inputText.trim()) { toast.warning("请输入约束描述"); return; }
    if (!selectedTaskId) return;
    setTranslating(true);
    setPreview([]);
    try {
      const result = await request.post(`/api/allocation-tasks/${selectedTaskId}/translate-constraint`, { text: inputText.trim() });
      if (result?.constraints) setPreview(result.constraints);
      else toast.error("翻译失败：返回格式异常");
    } catch (e: any) { toast.error("翻译请求失败: " + (e.message || "")); }
    finally { setTranslating(false); }
  }

  async function applyConstraints() {
    if (!selectedTaskId || preview.length === 0) return;
    const merged = [...constraints, ...preview];
    const payload = { llmOverrides: JSON.stringify({ overrides: merged }) };
    try {
      await request.put(`/api/allocation-tasks/${selectedTaskId}`, { generationConfig: { ...config, ...payload } });
      toast.success(`已应用 ${preview.length} 条约束`);
      setPreview([]); setInputText("");
      await loadConstraints();
    } catch (e: any) { toast.error("保存失败: " + (e.message || "")); }
  }

  async function removeConstraint(idx: number) {
    const updated = constraints.filter((_, i) => i !== idx);
    await saveAll(updated);
  }

  async function saveAll(list: Constraint[]) {
    if (!selectedTaskId) return;
    try {
      await request.put(`/api/allocation-tasks/${selectedTaskId}`, { generationConfig: { ...config, llmOverrides: JSON.stringify({ overrides: list }) } });
      setConstraints(list);
      toast.success("保存成功");
    } catch (e: any) { toast.error("保存失败"); }
  }

  function addBlank() {
    setConstraints([...constraints, { type: "HARD", targetType: "TEACHER", targetId: "", reason: "" }]);
  }

  return { tasks, selectedTaskId, setSelectedTaskId: (id: number) => { setSelectedTaskId(id); loadConstraints(id); }, constraints, loading, config, inputText, setInputText, translating, preview, setPreview, loadTasks, loadConstraints, translateInput, applyConstraints, removeConstraint, saveAll, addBlank };
}
