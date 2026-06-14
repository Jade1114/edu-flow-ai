interface Props {
  label: string;
  selectedCount: number;
  filteredCount: number;
  busy: boolean;
  disableSupported?: boolean;
  onSelectFiltered: () => void;
  onClearSelection: () => void;
  onDisable?: () => void;
  onDelete: () => void;
}

export default function BatchActionBar({
  label,
  selectedCount,
  filteredCount,
  busy,
  disableSupported = true,
  onSelectFiltered,
  onClearSelection,
  onDisable,
  onDelete,
}: Props) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-base-300 bg-base-100 px-3 py-2 text-sm">
      <div className="text-base-content/70">
        已选择 <span className="font-semibold text-base-content">{selectedCount}</span> 条{label}
        <span className="ml-2 text-base-content/40">筛选结果 {filteredCount} 条</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-xs btn-outline" disabled={busy || filteredCount === 0} onClick={onSelectFiltered}>
          全选筛选结果
        </button>
        <button className="btn btn-xs btn-ghost" disabled={busy || selectedCount === 0} onClick={onClearSelection}>
          取消选择
        </button>
        {disableSupported && (
          <button className="btn btn-xs btn-warning" disabled={busy || selectedCount === 0} onClick={onDisable}>
            {busy ? <span className="loading loading-spinner loading-xs" /> : "批量禁用"}
          </button>
        )}
        <button className="btn btn-xs btn-error" disabled={busy || selectedCount === 0} onClick={onDelete}>
          {busy ? <span className="loading loading-spinner loading-xs" /> : "批量删除"}
        </button>
      </div>
    </div>
  );
}
