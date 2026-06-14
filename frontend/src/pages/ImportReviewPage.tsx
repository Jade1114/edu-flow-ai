import { useState } from "react";
import { useImportReviews } from "../hooks/useImportReviews";

const DEFAULT_TEST_RAW_DIR = "backend/data/raw/2025-2026学年2学期总课表";
const DEFAULT_TEST_BATCH = "TEST_2025_2026_2";

export default function ImportReviewPage() {
  const review = useImportReviews();
  const selectedBatch = review.batches.find(batch => batch.id === review.selectedBatchId);
  const [rawDir, setRawDir] = useState(DEFAULT_TEST_RAW_DIR);
  const [taskBatch, setTaskBatch] = useState(DEFAULT_TEST_BATCH);
  const [clearExisting, setClearExisting] = useState(false);
  const [cleanupConfirmText, setCleanupConfirmText] = useState("");
  const [adminEmployeeNo, setAdminEmployeeNo] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("admin123");
  const [adminName, setAdminName] = useState("系统管理员");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">课表导入审核</h2>
          <p className="text-sm text-base-content/50 mt-1">每次课表导入会形成一个整体审核批次；确认入库只处理已决策项，未决策项会继续保留。</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-sm btn-outline" disabled={review.items.length === 0} onClick={review.fillRecommended}>填入推荐决策</button>
          <button className="btn btn-sm btn-ghost" disabled={review.items.length === 0} onClick={review.clearDecisions}>清空决策</button>
          <button className="btn btn-sm btn-primary" disabled={review.saving || review.items.length === 0} onClick={review.save}>
            {review.saving ? <span className="loading loading-spinner loading-xs" /> : "保存决策"}
          </button>
          <button className="btn btn-sm btn-outline" disabled={review.applying || review.items.length === 0} onClick={() => review.apply(false)}>
            {review.applying ? <span className="loading loading-spinner loading-xs" /> : "Dry-run 预演"}
          </button>
          <button className="btn btn-sm btn-success" disabled={review.applying || review.stats.decided === 0} onClick={() => review.apply(true)}>
            {review.applying ? <span className="loading loading-spinner loading-xs" /> : "确认入库"}
          </button>
          <button className="btn btn-sm btn-error btn-outline" disabled={review.loading || review.batches.length === 0} onClick={review.deleteCurrentBatch}>删除当前批次</button>
          <button className="btn btn-sm btn-error" disabled={review.loading || review.batches.length === 0} onClick={review.deleteAllBatches}>清空剩余批次</button>
        </div>
      </div>

      <div className="card bg-base-100 border border-error/30 bg-error/5 shadow-sm">
        <div className="card-body p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-error">测试数据清理</h3>
              <p className="text-xs text-base-content/60 mt-1">清空课程、教师、教室、班级、教学任务和排课结果；清理后会重建一个管理员账号。</p>
            </div>
            <button className="btn btn-sm btn-error" disabled={review.cleaningData || cleanupConfirmText !== "清理测试数据"} onClick={() => review.cleanupTestData(cleanupConfirmText, adminEmployeeNo, adminPassword, adminName)}>
              {review.cleaningData ? <span className="loading loading-spinner loading-xs" /> : "清理测试数据"}
            </button>
          </div>
          <div className="mt-3 grid grid-cols-1 lg:grid-cols-5 gap-3">
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">确认文本</span></div>
              <input className="input input-bordered input-sm" placeholder="输入：清理测试数据" value={cleanupConfirmText} onChange={event => setCleanupConfirmText(event.target.value)} />
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">管理员账号</span></div>
              <input className="input input-bordered input-sm font-mono text-xs" value={adminEmployeeNo} onChange={event => setAdminEmployeeNo(event.target.value)} />
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">管理员密码</span></div>
              <input className="input input-bordered input-sm font-mono text-xs" value={adminPassword} onChange={event => setAdminPassword(event.target.value)} />
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">管理员名称</span></div>
              <input className="input input-bordered input-sm" value={adminName} onChange={event => setAdminName(event.target.value)} />
            </label>
          </div>
          {review.cleanupResult && (
            <div className="mt-3 text-xs p-3 rounded-lg bg-success/10 text-success">
              <div className="font-medium mb-1">清理完成，管理员账号：{String(review.cleanupResult.adminEmployeeNo || "-")}</div>
              <div className="opacity-70 font-mono whitespace-pre-wrap max-h-32 overflow-auto">{JSON.stringify(review.cleanupResult.counts || [], null, 2)}</div>
            </div>
          )}
        </div>
      </div>

      <div className="card bg-base-100 border border-base-300 shadow-sm">
        <div className="card-body p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold">从原始课表生成审核批次</h3>
              <p className="text-xs text-base-content/50 mt-1">解析、全局去重并生成一个整体审核批次；不会直接写入数据库。</p>
            </div>
            <button className="btn btn-sm btn-primary" disabled={review.processingFolder} onClick={() => review.processFolder(rawDir, taskBatch, clearExisting)}>
              {review.processingFolder ? <span className="loading loading-spinner loading-xs" /> : "开始导入数据"}
            </button>
          </div>
          <div className="mt-3 grid grid-cols-1 lg:grid-cols-6 gap-3">
            <label className="form-control lg:col-span-3">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">原始课表目录</span></div>
              <input className="input input-bordered input-sm font-mono text-xs" value={rawDir} onChange={event => setRawDir(event.target.value)} />
            </label>
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">任务批次 task_batch</span></div>
              <input className="input input-bordered input-sm font-mono text-xs" value={taskBatch} onChange={event => setTaskBatch(event.target.value)} />
            </label>
            <label className="label cursor-pointer justify-start gap-2 pt-7">
              <input type="checkbox" className="checkbox checkbox-sm" checked={clearExisting} onChange={event => setClearExisting(event.target.checked)} />
              <span className="label-text text-xs">清空旧审核批次</span>
            </label>
          </div>
          {(review.processingFolder || review.processLogs.length > 0) && (
            <div className="mt-3 rounded-lg bg-neutral text-neutral-content p-3">
              <div className="mb-2 flex items-center justify-between text-xs font-medium">
                <span>实时导入日志</span>
                {review.processingFolder && <span className="loading loading-spinner loading-xs" />}
              </div>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{review.processLogs.join("\n") || "等待导入日志..."}</pre>
            </div>
          )}
          {review.processResult && review.processResult.status !== "RUNNING" && (
            <div className={`mt-3 text-xs p-3 rounded-lg ${review.processResult.status === "ok" ? "bg-success/10 text-success" : "bg-error/10 text-error"}`}>
              <div className="font-medium mb-1">{review.processResult.status === "ok" ? "审核批次生成完成" : "审核批次生成失败"}</div>
              <div className="opacity-70 font-mono whitespace-pre-wrap max-h-32 overflow-auto">{JSON.stringify(review.processResult, null, 2)}</div>
            </div>
          )}
        </div>
      </div>

      <div className="card bg-base-100 border border-base-300 shadow-sm">
        <div className="card-body p-4">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
            <label className="form-control lg:col-span-3">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">导入批次</span></div>
              <select className="select select-bordered select-sm" value={review.selectedBatchId} onChange={event => review.setSelectedBatchId(event.target.value)}>
                <option value={review.ALL_BATCHES}>全局批次优先</option>
                {review.batches.length === 0 && <option value="" disabled>暂无批次</option>}
                {review.batches.map(batch => <option key={batch.id} value={batch.id}>{batch.name}</option>)}
              </select>
            </label>
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">审核类型</span></div>
              <select className="select select-bordered select-sm" value={review.filter} onChange={event => review.setFilter(event.target.value)}>
                <option value="all">全部</option>
                <option value="pending">未决策</option>
                <option value="conflict">冲突项</option>
                <option value="new_item">新增项</option>
              </select>
            </label>
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">对象类型</span></div>
              <select className="select select-bordered select-sm" value={review.entityFilter} onChange={event => review.setEntityFilter(event.target.value)}>
                <option value="all">全部对象</option>
                {review.entityOptions.map(type => <option key={type} value={type}>{type}</option>)}
              </select>
            </label>
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">决策状态</span></div>
              <select className="select select-bordered select-sm" value={review.decisionFilter} onChange={event => review.setDecisionFilter(event.target.value)}>
                <option value="all">全部决策</option>
                <option value="undecided">未决策</option>
                <option value="decided">已决策</option>
                {review.decisionOptionsForFilter.map(option => <option key={option} value={option}>{review.decisionLabel(option)}</option>)}
              </select>
            </label>
            <label className="form-control lg:col-span-2">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">搜索</span></div>
              <input className="input input-bordered input-sm" placeholder="课程/教师/班级/教室/原因..." value={review.keyword} onChange={event => review.setKeyword(event.target.value)} />
            </label>
            <div className="flex items-end">
              <button className="btn btn-sm btn-outline w-full" onClick={review.reload} disabled={review.loading}>刷新</button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-base-content/50">
            <span>已加载 {review.items.length} 条，筛选后 {review.filteredItems.length} 条；当前仅渲染第 {review.page} / {review.totalPages} 页</span>
            <label className="flex items-center gap-2">
              <span>每页</span>
              <select className="select select-bordered select-xs" value={review.pageSize} onChange={event => review.setPageSize(Number(event.target.value))}>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
              </select>
            </label>
          </div>
          <div className="mt-3 text-xs text-base-content/50 truncate">
            {review.selectedBatchId === review.ALL_BATCHES ? `当前优先显示全局聚合批次；若不存在全局批次才显示全部单班批次` : selectedBatch?.path}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
        {["teacher", "classroom", "class_group", "course", "teaching_task"].map(layer => (
          <button
            key={layer}
            className={`btn h-auto justify-start p-3 ${review.layerFilter === layer ? "btn-primary" : "btn-outline"}`}
            onClick={() => review.setLayerFilter(layer)}
          >
            <span className="text-left">
              <span className="block font-semibold">{layerLabel(layer)}</span>
              <span className="block text-xs opacity-70">
                {review.layerStats[layer]?.total || 0} 条，未决策 {review.layerStats[layer]?.pending || 0}，忽略 {review.layerStats[layer]?.ignored || 0}
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="总审核项" value={review.stats.total} />
        <Stat label="已决策" value={review.stats.decided} tone="text-success" />
        <Stat label="未决策" value={review.stats.pending} tone={review.stats.pending > 0 ? "text-warning" : "text-success"} />
        <Stat label="冲突" value={review.stats.conflicts} tone="text-error" />
        <Stat label="新增" value={review.stats.newItems} tone="text-info" />
      </div>

      {review.applyResult && <ApplyResultCard result={review.applyResult} />}

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-base-300 bg-base-100 p-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-base-content/60">
          <span>已勾选 {review.selectedCount} 条</span>
          <button className="btn btn-xs btn-outline" onClick={() => review.selectPageItems(true)}>选择当前页</button>
          <button className="btn btn-xs btn-outline" onClick={() => review.selectFilteredItems(true)}>选择筛选结果</button>
          <button className="btn btn-xs btn-ghost" onClick={() => review.selectFilteredItems(false)}>清空筛选选择</button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-xs btn-success" onClick={() => review.bulkSetDecision("selected", "create")}>勾选新建</button>
          <button className="btn btn-xs btn-warning" onClick={() => review.bulkSetDecision("selected", "ignore")}>勾选禁用</button>
          <button className="btn btn-xs btn-error btn-outline" disabled={review.saving} onClick={() => review.deleteReviewItems("selected")}>勾选删除</button>
          <button className="btn btn-xs btn-outline" onClick={() => review.bulkSetDecision("page", "create")}>当前页新建</button>
          <button className="btn btn-xs btn-outline" onClick={() => review.bulkSetDecision("page", "ignore")}>当前页禁用</button>
          <button className="btn btn-xs btn-error btn-outline" disabled={review.saving} onClick={() => review.deleteReviewItems("page")}>当前页删除</button>
          <button className="btn btn-xs btn-outline" onClick={() => review.bulkSetDecision("filtered", "create")}>筛选结果新建</button>
          <button className="btn btn-xs btn-outline" onClick={() => review.bulkSetDecision("filtered", "ignore")}>筛选结果禁用</button>
          <button className="btn btn-xs btn-error" disabled={review.saving} onClick={() => review.deleteReviewItems("filtered")}>筛选结果删除</button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-base-300 bg-base-100">
        <table className="table table-zebra table-sm">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  className="checkbox checkbox-xs"
                  checked={review.pagedItems.length > 0 && review.pagedItems.every(item => review.isSelected(item))}
                  onChange={event => review.selectPageItems(event.target.checked)}
                />
              </th>
              <th>批次</th>
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
              <tr><td colSpan={11} className="text-center py-10"><span className="loading loading-spinner" /></td></tr>
            ) : review.filteredItems.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-10 text-base-content/40">暂无审核项</td></tr>
            ) : review.pagedItems.map(item => (
              <tr key={`${item.batchId}:${item.reviewId}`}>
                <td>
                  <input
                    type="checkbox"
                    className="checkbox checkbox-xs"
                    checked={review.isSelected(item)}
                    onChange={event => review.toggleSelected(item, event.target.checked)}
                  />
                </td>
                <td className="max-w-[180px] truncate font-mono text-[10px]" title={item.batchId}>{item.batchId || "-"}</td>
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
                  <select className="select select-bordered select-xs min-w-36" value={item.decision || ""} onChange={event => review.updateDecision(item.batchId, item.reviewId, event.target.value)}>
                    <option value="">未选择</option>
                    {review.decisionOptions(item).map(option => <option key={option} value={option}>{review.decisionLabel(option)}</option>)}
                  </select>
                </td>
                <td className="max-w-[320px] truncate text-xs text-base-content/60" title={[item.reason, item.reviewNote].filter(Boolean).join("；")}>
                  {item.reason}
                  {item.reviewNote && <div className="text-warning">{item.reviewNote}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <div className="text-xs text-base-content/50">
          当前显示 {review.pagedItems.length} 条 / 筛选后 {review.filteredItems.length} 条 / 全部 {review.items.length} 条
        </div>
        <div className="join">
          <button className="btn btn-sm join-item" disabled={review.page <= 1} onClick={() => review.setPage(1)}>首页</button>
          <button className="btn btn-sm join-item" disabled={review.page <= 1} onClick={() => review.setPage(Math.max(1, review.page - 1))}>上一页</button>
          <button className="btn btn-sm join-item btn-ghost">{review.page} / {review.totalPages}</button>
          <button className="btn btn-sm join-item" disabled={review.page >= review.totalPages} onClick={() => review.setPage(Math.min(review.totalPages, review.page + 1))}>下一页</button>
          <button className="btn btn-sm join-item" disabled={review.page >= review.totalPages} onClick={() => review.setPage(review.totalPages)}>末页</button>
        </div>
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

function layerLabel(layer: string) {
  const labels: Record<string, string> = {
    teacher: "教师",
    classroom: "教室",
    class_group: "班级",
    course: "课程",
    teaching_task: "教学任务",
  };
  return labels[layer] || layer;
}
