import { useEffect, useMemo, useState } from "react";
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

const decisionLabels: Record<string, string> = {
  keep_db: "保留数据库",
  use_import: "使用导入值",
  create: "新建",
  create_after_dependencies: "依赖就绪后新建",
  ignore: "忽略",
};

export function useImportReviews() {
  const [batches, setBatches] = useState<ImportReviewBatch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [items, setItems] = useState<ImportReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("all");

  useEffect(() => { loadBatches(); }, []);
  useEffect(() => { if (selectedBatchId) loadItems(selectedBatchId); }, [selectedBatchId]);

  async function loadBatches() {
    setLoading(true);
    try {
      const data = await request.get<ImportReviewBatch[]>("/api/import-reviews/batches");
      const next = Array.isArray(data) ? data : [];
      setBatches(next);
      if (!selectedBatchId && next.length > 0) setSelectedBatchId(next[0].id);
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
      const data = await request.get<ImportReviewItem[]>(`/api/import-reviews/batches/${encodeURIComponent(batchId)}/items`);
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      toast.error("导入审核项加载失败");
      throw error;
    } finally {
      setLoading(false);
    }
  }

  function updateDecision(reviewId: string, decision: string) {
    setItems(current => current.map(item => item.reviewId === reviewId ? { ...item, decision } : item));
  }

  function fillRecommended() {
    setItems(current => current.map(item => ({ ...item, decision: item.recommendedDecision || item.decision })));
    toast.success("已填入推荐决策");
  }

  function clearDecisions() {
    setItems(current => current.map(item => ({ ...item, decision: "" })));
  }

  async function save() {
    if (!selectedBatchId) return;
    setSaving(true);
    try {
      await request.put(`/api/import-reviews/batches/${encodeURIComponent(selectedBatchId)}/items`, { items });
      toast.success("审核决策已保存");
      await loadBatches();
    } catch (error) {
      toast.error("保存审核决策失败");
      throw error;
    } finally {
      setSaving(false);
    }
  }

  const filteredItems = useMemo(() => {
    if (filter === "pending") return items.filter(item => !item.decision);
    if (filter === "conflict") return items.filter(item => item.reviewType === "conflict");
    if (filter === "new_item") return items.filter(item => item.reviewType === "new_item");
    return items;
  }, [items, filter]);

  const stats = useMemo(() => ({
    total: items.length,
    pending: items.filter(item => !item.decision).length,
    conflicts: items.filter(item => item.reviewType === "conflict").length,
    newItems: items.filter(item => item.reviewType === "new_item").length,
    decided: items.filter(item => item.decision).length,
  }), [items]);

  function decisionOptions(item: ImportReviewItem) {
    return (item.allowedDecisions || "").split(",").map(value => value.trim()).filter(Boolean);
  }

  function decisionLabel(value: string) {
    return decisionLabels[value] || value || "未选择";
  }

  return {
    batches, selectedBatchId, setSelectedBatchId,
    items, filteredItems, loading, saving,
    filter, setFilter, stats,
    updateDecision, fillRecommended, clearDecisions, save,
    decisionOptions, decisionLabel,
    reload: () => selectedBatchId ? loadItems(selectedBatchId) : loadBatches(),
  };
}
