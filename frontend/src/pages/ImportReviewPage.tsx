import { useImportReviews } from "../hooks/useImportReviews";

export default function ImportReviewPage() {
  const review = useImportReviews();
  const selectedBatch = review.batches.find(batch => batch.id === review.selectedBatchId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">课表导入审核</h2>
          <p className="text-sm text-base-content/50 mt-1">对齐导入课表与基础数据库，手动选择冲突和新增项的处理方式。</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-sm btn-outline" disabled={review.items.length === 0} onClick={review.fillRecommended}>填入推荐决策</button>
          <button className="btn btn-sm btn-ghost" disabled={review.items.length === 0} onClick={review.clearDecisions}>清空决策</button>
          <button className="btn btn-sm btn-primary" disabled={review.saving || !review.selectedBatchId} onClick={review.save}>
            {review.saving ? <span className="loading loading-spinner loading-xs" /> : "保存决策"}
          </button>
          <button className="btn btn-sm btn-outline" disabled={review.applying || !review.selectedBatchId || review.items.length === 0} onClick={() => review.apply(false)}>
            {review.applying ? <span className="loading loading-spinner loading-xs" /> : "Dry-run 预演"}
          </button>
          <button className="btn btn-sm btn-success" disabled={review.applying || !review.selectedBatchId || review.stats.pending > 0 || review.items.length === 0} onClick={() => review.apply(true)}>
            {review.applying ? <span className="loading loading-spinner loading-xs" /> : "确认入库"}
          </button>
        </div>
      </div>

      <div className="card bg-base-100 border border-base-300 shadow-sm">
        <div className="card-body p-4">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">导入批次</span></div>
              <select className="select select-bordered select-sm" value={review.selectedBatchId} onChange={event => review.setSelectedBatchId(event.target.value)}>
                {review.batches.length === 0 && <option value="">暂无批次</option>}
                {review.batches.map(batch => <option key={batch.id} value={batch.id}>{batch.name}</option>)}
              </select>
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">筛选</span></div>
              <select className="select select-bordered select-sm" value={review.filter} onChange={event => review.setFilter(event.target.value)}>
                <option value="all">全部</option>
                <option value="pending">未决策</option>
                <option value="conflict">冲突项</option>
                <option value="new_item">新增项</option>
              </select>
            </label>
            <div className="flex items-end">
              <button className="btn btn-sm btn-outline w-full" onClick={review.reload} disabled={review.loading}>刷新</button>
            </div>
          </div>
          {selectedBatch && <div className="mt-3 text-xs text-base-content/50 truncate">{selectedBatch.path}</div>}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="总审核项" value={review.stats.total} />
        <Stat label="已决策" value={review.stats.decided} tone="text-success" />
        <Stat label="未决策" value={review.stats.pending} tone={review.stats.pending > 0 ? "text-warning" : "text-success"} />
        <Stat label="冲突" value={review.stats.conflicts} tone="text-error" />
        <Stat label="新增" value={review.stats.newItems} tone="text-info" />
      </div>

      {review.applyResult && <ApplyResultCard result={review.applyResult} />}

      <div className="overflow-x-auto rounded-lg border border-base-300 bg-base-100">
        <table className="table table-zebra table-sm">
          <thead>
            <tr>
              <th>ID</th>
              <th>类型</th>
              <th>对象</th>
              <th>字段</th>
              <th>数据库</th>
              <th>导入</th>
              <th>推荐</th>
              <th>决策</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            {review.loading ? (
              <tr><td colSpan={9} className="text-center py-10"><span className="loading loading-spinner" /></td></tr>
            ) : review.filteredItems.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-10 text-base-content/40">暂无审核项</td></tr>
            ) : review.filteredItems.map(item => (
              <tr key={item.reviewId}>
                <td className="font-mono text-xs">{item.reviewId}</td>
                <td><ReviewBadge type={item.reviewType} /></td>
                <td>
                  <div className="font-medium max-w-[220px] truncate" title={item.displayName}>{item.displayName}</div>
                  <div className="text-[10px] text-base-content/40 font-mono max-w-[220px] truncate" title={item.entityKey}>{item.entityType}:{item.entityKey}</div>
                </td>
                <td>{item.fieldLabel || <span className="text-base-content/30">-</span>}</td>
                <td className="max-w-[160px] truncate" title={item.dbValue}>{item.dbValue || <span className="text-base-content/30">-</span>}</td>
                <td className="max-w-[160px] truncate" title={item.importValue}>{item.importValue || <span className="text-base-content/30">-</span>}</td>
                <td><span className="badge badge-outline badge-sm">{review.decisionLabel(item.recommendedDecision)}</span></td>
                <td>
                  <select className="select select-bordered select-xs min-w-36" value={item.decision || ""} onChange={event => review.updateDecision(item.reviewId, event.target.value)}>
                    <option value="">未选择</option>
                    {review.decisionOptions(item).map(option => <option key={option} value={option}>{review.decisionLabel(option)}</option>)}
                  </select>
                </td>
                <td className="max-w-[260px] truncate text-xs text-base-content/60" title={item.reason}>{item.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ApplyResultCard({ result }: { result: Record<string, any> }) {
  const raw = String(result.rawOutput || "");
  let parsed: any = null;
  try { parsed = raw ? JSON.parse(raw) : null; } catch { parsed = null; }
  const counts = parsed?.planned_counts || parsed?.plannedCounts || {};
  return (
    <div className="card bg-base-100 border border-base-300 shadow-sm">
      <div className="card-body p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="font-semibold">{result.execute ? "入库执行结果" : "Dry-run 预演结果"}</div>
            <div className="text-xs text-base-content/50 mt-1">{result.reportPath}</div>
          </div>
          <span className={`badge ${result.execute ? "badge-success" : "badge-info"}`}>{result.execute ? "已写库" : "未写库"}</span>
        </div>
        {parsed && (
          <div className="flex flex-wrap gap-2 mt-3 text-xs">
            <span className="badge badge-ghost">决策 {parsed.decision_count ?? 0}</span>
            <span className="badge badge-ghost">计划 {parsed.planned_count ?? 0}</span>
            <span className="badge badge-ghost">跳过 {parsed.skipped_count ?? 0}</span>
            {Object.entries(counts).map(([key, value]) => <span key={key} className="badge badge-outline">{key}: {String(value)}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, tone = "text-primary" }: { label: string; value: number; tone?: string }) {
  return (
    <div className="stat bg-base-100 border border-base-300 rounded-lg p-3">
      <div className="stat-title text-xs">{label}</div>
      <div className={`stat-value text-lg ${tone}`}>{value}</div>
    </div>
  );
}

function ReviewBadge({ type }: { type: string }) {
  if (type === "conflict") return <span className="badge badge-error badge-sm">冲突</span>;
  if (type === "new_item") return <span className="badge badge-info badge-sm">新增</span>;
  return <span className="badge badge-ghost badge-sm">{type}</span>;
}
