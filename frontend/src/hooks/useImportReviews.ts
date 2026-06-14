import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import request from "../api/request";

export interface ImportReviewBatch {
  id: string;
  name: string;
  path: string;
  reviewItemCount: number;
  pendingCount: number;
  conflictCount: number;
  newItemCount: number;
  hasReviewFile: boolean;
}

export interface ImportReviewItem {
  batchId: string;
  reviewId: string;
  reviewType: string;
  entityType: string;
  entityKey: string;
  displayName: string;
  fieldName: string;
  fieldLabel: string;
  dbId: string;
  dbValue: string;
  importValue: string;
  status: string;
  decision: string;
  allowedDecisions: string;
  recommendedDecision: string;
  reason: string;
  reviewNote: string;
}

const ALL_BATCHES = "__ALL__";
const LAYERS = ["teacher", "classroom", "class_group", "course", "teaching_task"] as const;

const decisionLabels: Record<string, string> = {
  keep_db: "保留数据库",
  use_import: "使用导入值",
  create: "新建",
  create_after_dependencies: "依赖就绪后新建",
  ignore: "忽略",
};

export function useImportReviews() {
  const [batches, setBatches] = useState<ImportReviewBatch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState(ALL_BATCHES);
  const [items, setItems] = useState<ImportReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [processingFolder, setProcessingFolder] = useState(false);
  const [cleaningData, setCleaningData] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<Record<string, any> | null>(null);
  const [processLogs, setProcessLogs] = useState<string[]>([]);
  const [processResult, setProcessResult] = useState<Record<string, any> | null>(null);
  const processEventSourceRef = useRef<EventSource | null>(null);
  const [applyResult, setApplyResult] = useState<Record<string, any> | null>(null);
  const [filter, setFilter] = useState("all");
  const [layerFilter, setLayerFilter] = useState("teacher");
  const [entityFilter, setEntityFilter] = useState("all");
  const [decisionFilter, setDecisionFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadBatches();
    return () => processEventSourceRef.current?.close();
  }, []);
  useEffect(() => { loadItems(selectedBatchId); }, [selectedBatchId]);
  useEffect(() => { setPage(1); }, [filter, layerFilter, entityFilter, decisionFilter, keyword, pageSize, selectedBatchId]);
  useEffect(() => { setSelectedIds(new Set()); }, [filter, layerFilter, entityFilter, decisionFilter, keyword, pageSize, selectedBatchId]);
  useEffect(() => {
    setSelectedIds(current => new Set([...current].filter(id => items.some(item => itemId(item) === id))));
  }, [items]);

  async function loadBatches() {
    setLoading(true);
    try {
      const data = await request.get<ImportReviewBatch[]>("/api/import-reviews/batches");
      const next = Array.isArray(data) ? data : [];
      setBatches(next);
      return next;
    } catch (error) {
      toast.error("导入审核批次加载失败");
      throw error;
    } finally {
      setLoading(false);
    }
  }

  async function loadItems(batchId: string) {
    setLoading(true);
    try {
      const url = batchId === ALL_BATCHES
        ? "/api/import-reviews/items"
        : `/api/import-reviews/batches/${encodeURIComponent(batchId)}/items`;
      const data = await request.get<ImportReviewItem[]>(url);
      setItems(dedupeItems(Array.isArray(data) ? data : []));
    } catch (error) {
      toast.error("导入审核项加载失败");
      throw error;
    } finally {
      setLoading(false);
    }
  }

  function updateDecision(batchId: string, reviewId: string, decision: string) {
    setItems(current => cascadeDecisions(current.map(item => item.batchId === batchId && item.reviewId === reviewId ? { ...item, decision } : item)));
  }

  function fillRecommended() {
    setItems(current => current.map(item => ({ ...item, decision: item.recommendedDecision || item.decision })));
    toast.success("已填入推荐决策");
  }

  function clearDecisions() {
    setItems(current => current.map(item => ({ ...item, decision: "" })));
  }

  function toggleSelected(item: ImportReviewItem, checked: boolean) {
    const id = itemId(item);
    setSelectedIds(current => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function selectPageItems(checked: boolean) {
    setSelectedIds(current => {
      const next = new Set(current);
      for (const item of pagedItems) {
        if (checked) next.add(itemId(item));
        else next.delete(itemId(item));
      }
      return next;
    });
  }

  function selectFilteredItems(checked: boolean) {
    setSelectedIds(current => {
      const next = new Set(current);
      for (const item of filteredItems) {
        if (checked) next.add(itemId(item));
        else next.delete(itemId(item));
      }
      return next;
    });
  }

  function bulkSetDecision(scope: "selected" | "page" | "filtered", decision: string) {
    const targetIds = targetIdsForScope(scope);
    if (targetIds.size === 0) {
      toast.warning("没有可批量处理的审核项");
      return;
    }
    setItems(current => cascadeDecisions(current.map(item => targetIds.has(itemId(item)) ? { ...item, decision } : item)));
    setSelectedIds(new Set());
    toast.success(`已批量设置 ${targetIds.size} 条`);
  }

  async function deleteReviewItems(scope: "selected" | "page" | "filtered") {
    const targetIds = targetIdsForScope(scope);
    if (targetIds.size === 0) {
      toast.warning("没有可删除的审核项");
      return;
    }
    const nextItems = deleteItemsWithDependents(items, targetIds);
    const deletedCount = items.length - nextItems.length;
    if (!confirm(`确认直接删除 ${deletedCount} 条审核数据？删除后会立即写入当前批次。`)) return;
    setSaving(true);
    try {
      await persistItems(nextItems);
      setItems(nextItems);
      setSelectedIds(new Set());
      toast.success(`已删除 ${deletedCount} 条审核数据`);
      await loadBatches();
    } catch (error) {
      toast.error("删除审核数据失败");
      throw error;
    } finally {
      setSaving(false);
    }
  }

  function targetIdsForScope(scope: "selected" | "page" | "filtered") {
    const filteredIds = new Set(filteredItems.map(itemId));
    return new Set(
      scope === "selected" ? [...selectedIds].filter(id => filteredIds.has(id))
        : (scope === "page" ? pagedItems : filteredItems).map(itemId)
    );
  }

  function processFolder(rawDir: string, taskBatch: string, clearExisting: boolean) {
    if (!rawDir.trim()) { toast.error("请填写原始课表目录"); return; }
    processEventSourceRef.current?.close();
    setProcessingFolder(true);
    setProcessLogs([]);
    setProcessResult({ status: "RUNNING" });

    const params = new URLSearchParams({
      rawDir: rawDir.trim(),
      taskBatch: taskBatch.trim() || "DEFAULT",
      clearExisting: String(clearExisting),
    });
    const source = new EventSource(`/api/import-reviews/process-folder/stream?${params.toString()}`);
    processEventSourceRef.current = source;

    source.addEventListener("log", (event) => {
      setProcessLogs(current => [...current, event.data]);
    });
    source.addEventListener("done", async (event) => {
      try { setProcessResult(JSON.parse(event.data)); }
      catch { setProcessResult({ status: "ok", rawOutput: event.data }); }
      setProcessingFolder(false);
      toast.success("导入审核批次已生成");
      source.close();
      processEventSourceRef.current = null;
      const nextBatches = await loadBatches();
      const globalBatch = [...nextBatches].reverse().find(batch => batch.id.startsWith("_global_"));
      setSelectedBatchId(globalBatch?.id || nextBatches[0]?.id || ALL_BATCHES);
    });
    source.addEventListener("failed", (event) => {
      let message = event.data || "未知错误";
      try { message = JSON.parse(event.data).message || message; } catch {}
      setProcessResult({ status: "FAILED", error: message });
      setProcessingFolder(false);
      toast.error(`生成审核批次失败: ${message}`);
      source.close();
      processEventSourceRef.current = null;
    });
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return;
      setProcessResult({ status: "FAILED", error: "导入审核日志连接中断" });
      setProcessingFolder(false);
      toast.error("导入审核日志连接中断");
      source.close();
      processEventSourceRef.current = null;
    };
  }

  async function cleanupTestData(confirmText: string, adminEmployeeNo: string, adminPassword: string, adminName: string) {
    if (confirmText !== "清理测试数据") {
      toast.error("请输入正确确认文本：清理测试数据");
      return;
    }
    if (!confirm("确认清理测试数据？这会删除课程、教师、教室、班级、教学任务和排课结果，并重建管理员账号。")) return;
    setCleaningData(true);
    try {
      const result = await request.post<Record<string, any>>("/api/maintenance/cleanup-test-data", {
        confirmText, adminEmployeeNo, adminPassword, adminName,
      });
      setCleanupResult(result || null);
      setItems([]);
      setApplyResult(null);
      toast.success("测试数据已清理，管理员账号已保留");
      await loadBatches();
    } catch (error) {
      toast.error("测试数据清理失败");
      throw error;
    } finally {
      setCleaningData(false);
    }
  }

  async function save() {
    setSaving(true);
    try {
      await persistItems(items);
      toast.success(selectedBatchId === ALL_BATCHES ? "全部审核决策已保存" : "审核决策已保存");
      await loadBatches();
    } catch (error) {
      toast.error("保存审核决策失败");
      throw error;
    } finally {
      setSaving(false);
    }
  }

  function persistItems(nextItems: ImportReviewItem[]) {
    const url = selectedBatchId === ALL_BATCHES
      ? "/api/import-reviews/items"
      : `/api/import-reviews/batches/${encodeURIComponent(selectedBatchId)}/items`;
    return request.put(url, { items: nextItems });
  }

  async function apply(execute: boolean) {
    const decidedCount = items.filter(item => item.decision).length;
    if (decidedCount === 0) {
      toast.error("请先选择要入库或忽略的审核项");
      return;
    }
    if (execute && !confirm(`确认处理 ${decidedCount} 条已决策审核项？已入库或忽略的项会从当前批次中移除，未决策项会保留。`)) return;
    setApplying(true);
    try {
      const saveUrl = selectedBatchId === ALL_BATCHES
        ? "/api/import-reviews/items"
        : `/api/import-reviews/batches/${encodeURIComponent(selectedBatchId)}/items`;
      const applyUrl = selectedBatchId === ALL_BATCHES
        ? "/api/import-reviews/apply-all"
        : `/api/import-reviews/batches/${encodeURIComponent(selectedBatchId)}/apply`;
      await request.put(saveUrl, { items });
      const result = await request.post<Record<string, any>>(applyUrl, { execute });
      setApplyResult(result || null);
      toast.success(execute ? "已处理已决策项，未决策项已保留" : "Dry-run 预演完成");
      await loadBatches();
      await loadItems(selectedBatchId);
    } catch (error) {
      toast.error(execute ? "入库执行失败" : "Dry-run 预演失败");
      throw error;
    } finally {
      setApplying(false);
    }
  }

  async function deleteCurrentBatch() {
    if (selectedBatchId === ALL_BATCHES) {
      await deleteAllBatches();
      return;
    }
    if (!confirm("确认删除当前导入审核批次？这只会删除解析/审核临时数据，不会删除已入库的数据。")) return;
    setLoading(true);
    try {
      await request.delete(`/api/import-reviews/batches/${encodeURIComponent(selectedBatchId)}`);
      toast.success("当前批次已删除");
      setItems([]);
      const next = await loadBatches();
      setSelectedBatchId(next[0]?.id || ALL_BATCHES);
    } catch (error) {
      toast.error("删除当前批次失败");
      throw error;
    } finally {
      setLoading(false);
    }
  }

  async function deleteAllBatches() {
    if (!confirm("确认删除所有剩余导入审核批次？这只会删除解析/审核临时数据，不会删除已入库的数据。")) return;
    setLoading(true);
    try {
      await request.delete("/api/import-reviews/batches");
      setItems([]);
      setSelectedIds(new Set());
      setSelectedBatchId(ALL_BATCHES);
      await loadBatches();
      toast.success("剩余导入审核批次已清空");
    } catch (error) {
      toast.error("清空导入审核批次失败");
      throw error;
    } finally {
      setLoading(false);
    }
  }

  const filteredItems = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    return items.filter(item => {
      if (filter === "pending" && item.decision) return false;
      if (filter === "conflict" && item.reviewType !== "conflict") return false;
      if (filter === "new_item" && item.reviewType !== "new_item") return false;
      if (layerFilter !== "all" && item.entityType !== layerFilter) return false;
      if (entityFilter !== "all" && item.entityType !== entityFilter) return false;
      if (decisionFilter === "decided" && !item.decision) return false;
      if (decisionFilter === "undecided" && item.decision) return false;
      if (decisionFilter !== "all" && decisionFilter !== "decided" && decisionFilter !== "undecided" && item.decision !== decisionFilter) return false;
      if (!query) return true;
      return [item.batchId, item.reviewId, item.reviewType, item.entityType, item.entityKey, item.displayName, item.fieldName, item.fieldLabel, item.dbValue, item.importValue, item.recommendedDecision, item.reason]
        .some(value => String(value || "").toLowerCase().includes(query));
    });
  }, [items, filter, layerFilter, entityFilter, decisionFilter, keyword]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, currentPage, pageSize]);

  const entityOptions = useMemo(() => Array.from(new Set(items.map(item => item.entityType).filter(Boolean))).sort(), [items]);
  const decisionOptionsForFilter = useMemo(() => Array.from(new Set(items.map(item => item.decision).filter(Boolean))).sort(), [items]);

  const stats = useMemo(() => ({
    total: items.length,
    pending: items.filter(item => !item.decision).length,
    conflicts: items.filter(item => item.reviewType === "conflict").length,
    newItems: items.filter(item => item.reviewType === "new_item").length,
    decided: items.filter(item => item.decision).length,
  }), [items]);

  const layerStats = useMemo(() => {
    const result: Record<string, { total: number; pending: number; ignored: number }> = {};
    for (const layer of LAYERS) result[layer] = { total: 0, pending: 0, ignored: 0 };
    for (const item of items) {
      if (!result[item.entityType]) continue;
      result[item.entityType].total++;
      if (!item.decision) result[item.entityType].pending++;
      if (item.decision === "ignore") result[item.entityType].ignored++;
    }
    return result;
  }, [items]);

  function decisionOptions(item: ImportReviewItem) {
    return (item.allowedDecisions || "").split(",").map(value => value.trim()).filter(Boolean);
  }

  function decisionLabel(value: string) {
    return decisionLabels[value] || value || "未选择";
  }

  function isSelected(item: ImportReviewItem) {
    return selectedIds.has(itemId(item));
  }

  const selectedCount = useMemo(() => {
    const filteredIds = new Set(filteredItems.map(itemId));
    return [...selectedIds].filter(id => filteredIds.has(id)).length;
  }, [filteredItems, selectedIds]);

  return {
    ALL_BATCHES,
    batches, selectedBatchId, setSelectedBatchId,
    items, filteredItems, pagedItems, loading, saving, applying, processingFolder, cleaningData, processLogs, processResult, cleanupResult, applyResult,
    filter, setFilter, layerFilter, setLayerFilter, entityFilter, setEntityFilter, decisionFilter, setDecisionFilter, keyword, setKeyword,
    page: currentPage, setPage, pageSize, setPageSize, totalPages, entityOptions, decisionOptionsForFilter, stats, layerStats,
    selectedCount, isSelected, toggleSelected, selectPageItems, selectFilteredItems, bulkSetDecision, deleteReviewItems,
    updateDecision, fillRecommended, clearDecisions, processFolder, cleanupTestData, save, apply,
    deleteCurrentBatch, deleteAllBatches,
    decisionOptions, decisionLabel,
    reload: () => loadItems(selectedBatchId),
  };
}

function itemId(item: ImportReviewItem) {
  return `${item.batchId}:${item.reviewId}`;
}

function dedupeItems(items: ImportReviewItem[]) {
  const seen = new Set<string>();
  const result: ImportReviewItem[] = [];
  for (const item of items) {
    const key = [item.batchId, item.reviewType, item.entityType, item.entityKey, item.fieldName].join("::");
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function cascadeDecisions(items: ImportReviewItem[]) {
  const ignoredCourses = new Set(items.filter(isIgnoredDependency("course")).map(item => item.entityKey));
  const ignoredTeachers = new Set(items.filter(isIgnoredDependency("teacher")).map(item => item.entityKey));
  const ignoredClassrooms = new Set(items.filter(isIgnoredDependency("classroom")).map(item => item.entityKey));
  const ignoredClassGroups = new Set(items.filter(isIgnoredDependency("class_group")).map(item => item.entityKey));
  if (ignoredCourses.size === 0 && ignoredTeachers.size === 0 && ignoredClassrooms.size === 0 && ignoredClassGroups.size === 0) return items;
  return items.map(item => {
    if (item.entityType !== "teaching_task" || item.decision === "ignore") return item;
    const deps = teachingTaskDependencies(item);
    const blocked = ignoredCourses.has(deps.course)
      || deps.teachers.some(name => ignoredTeachers.has(name))
      || deps.classGroups.some(name => ignoredClassGroups.has(name))
      || deps.classrooms.some(name => ignoredClassrooms.has(name));
    return blocked ? { ...item, decision: "ignore", reviewNote: appendReviewNote(item.reviewNote, "依赖项已取消，自动取消导入") } : item;
  });
}

function deleteItemsWithDependents(items: ImportReviewItem[], targetIds: Set<string>) {
  const directDeleteItems = items.filter(item => targetIds.has(itemId(item)));
  const deletedCourses = new Set(directDeleteItems.filter(item => item.entityType === "course").map(item => item.entityKey));
  const deletedTeachers = new Set(directDeleteItems.filter(item => item.entityType === "teacher").map(item => item.entityKey));
  const deletedClassrooms = new Set(directDeleteItems.filter(item => item.entityType === "classroom").map(item => item.entityKey));
  const deletedClassGroups = new Set(directDeleteItems.filter(item => item.entityType === "class_group").map(item => item.entityKey));
  return items.filter(item => {
    if (targetIds.has(itemId(item))) return false;
    if (item.entityType !== "teaching_task") return true;
    const deps = teachingTaskDependencies(item);
    return !deletedCourses.has(deps.course)
      && !deps.teachers.some(name => deletedTeachers.has(name))
      && !deps.classGroups.some(name => deletedClassGroups.has(name))
      && !deps.classrooms.some(name => deletedClassrooms.has(name));
  });
}

function isIgnoredDependency(entityType: string) {
  return (item: ImportReviewItem) => item.entityType === entityType && item.decision === "ignore";
}

function teachingTaskDependencies(item: ImportReviewItem) {
  const [course = "", classGroupsText = "", teachersText = ""] = item.entityKey.split("|");
  return {
    course,
    classGroups: splitDependencyNames(classGroupsText),
    teachers: splitDependencyNames(teachersText),
    classrooms: parseDependencyList(item.reason, "classrooms"),
  };
}

function parseDependencyList(text: string, key: string) {
  const match = String(text || "").match(new RegExp(`${key}=([^；;]+)`));
  return splitDependencyNames(match?.[1] || "");
}

function splitDependencyNames(text: string) {
  return String(text || "").split(/[|,，、]/).map(value => value.trim()).filter(Boolean);
}

function appendReviewNote(current: string, note: string) {
  return current?.includes(note) ? current : [current, note].filter(Boolean).join("；");
}
