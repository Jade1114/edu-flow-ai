import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import request from "../api/request";

interface Identifiable {
  id: number | null;
}

interface Options<T extends Identifiable> {
  entity: string;
  label: string;
  items: T[];
  filtered: T[];
  paged: T[];
  reload: () => Promise<void>;
  disableSupported?: boolean;
}

export function useBatchSelection<T extends Identifiable>({
  entity,
  label,
  items,
  filtered,
  paged,
  reload,
  disableSupported = true,
}: Options<T>) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchBusy, setBatchBusy] = useState(false);

  const pagedIds = useMemo(() => compactIds(paged), [paged]);
  const filteredIds = useMemo(() => compactIds(filtered), [filtered]);
  const selectedCount = selectedIds.length;
  const pageSelected = pagedIds.length > 0 && pagedIds.every(id => selectedIds.includes(id));
  const pageIndeterminate = pagedIds.some(id => selectedIds.includes(id)) && !pageSelected;

  useEffect(() => {
    const available = new Set(compactIds(items));
    setSelectedIds(prev => prev.filter(id => available.has(id)));
  }, [items]);

  function clearSelection() {
    setSelectedIds([]);
  }

  function toggleSelected(id: number) {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]);
  }

  function togglePageSelected() {
    setSelectedIds(prev => {
      if (pageSelected) return prev.filter(id => !pagedIds.includes(id));
      return Array.from(new Set([...prev, ...pagedIds]));
    });
  }

  function selectFiltered() {
    setSelectedIds(filteredIds);
  }

  async function batchDisable() {
    if (!disableSupported || selectedIds.length === 0) return;
    if (!confirm(`确认禁用已选择的 ${selectedIds.length} 条${label}？`)) return;
    setBatchBusy(true);
    try {
      await request.post(`/api/management/${entity}/batch-disable`, { ids: selectedIds });
      toast.success(`已禁用 ${selectedIds.length} 条${label}`);
      clearSelection();
      await reload();
    } finally {
      setBatchBusy(false);
    }
  }

  async function batchDelete() {
    if (selectedIds.length === 0) return;
    if (!confirm(`确认永久删除已选择的 ${selectedIds.length} 条${label}？删除后不可恢复。`)) return;
    setBatchBusy(true);
    try {
      await request.post(`/api/management/${entity}/batch-delete`, { ids: selectedIds });
      toast.success(`已删除 ${selectedIds.length} 条${label}`);
      clearSelection();
      await reload();
    } finally {
      setBatchBusy(false);
    }
  }

  return {
    selectedIds,
    selectedCount,
    pageSelected,
    pageIndeterminate,
    batchBusy,
    disableSupported,
    clearSelection,
    toggleSelected,
    togglePageSelected,
    selectFiltered,
    batchDisable,
    batchDelete,
  };
}

function compactIds<T extends Identifiable>(items: T[]) {
  return items.map(item => item.id).filter((id): id is number => typeof id === "number");
}
