import { useAllocation } from "../hooks/useAllocation";

export default function AllocationManager() {
  const a = useAllocation();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2>分课任务</h2>
        <button className="btn btn-primary btn-sm" onClick={() => a.openTaskDialog()}>新增排课任务</button>
      </div>

      {/* Tasks table */}
      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead><tr><th>ID</th><th>任务名称</th><th>方案数</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            {a.loading ? <tr><td colSpan={5} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : a.tasks.length === 0 ? <tr><td colSpan={5} className="text-center py-8 text-base-content/40">暂无排课任务</td></tr>
            : a.tasks.map(t => <tr key={t.id}><td>{t.id}</td><td className="font-medium cursor-pointer hover:text-primary" onClick={() => a.selectTask(t)}>{t.name || `任务 #${t.id}`}</td><td>{t.schemeCount ?? "-"}</td><td><span className={`badge badge-xs ${t.status === "ACTIVE" ? "badge-success" : "badge-ghost"}`}>{t.status}</span></td>
              <td><div className="flex gap-1"><button className="btn btn-xs btn-ghost" onClick={() => a.openTaskDialog(t)}>编辑</button><button className="btn btn-xs btn-ghost text-error" onClick={() => a.deleteTask(t.id)}>删除</button></div></td></tr>)}
          </tbody>
        </table>
      </div>

      {/* Selected task -> schemes */}
      {a.selectedTask && (
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold">方案列表 — {a.selectedTask.name || `任务 #${a.selectedTask.id}`}</span>
              <button className="btn btn-warning btn-sm" disabled={a.generating} onClick={a.generateSchemes}>
                {a.generating ? <><span className="loading loading-spinner loading-xs" /> {a.generateStatus}</> : "生成排课方案"}
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="table table-sm table-zebra">
                <thead><tr><th>ID</th><th>方案名</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
                <tbody>
                  {a.schemesLoading ? <tr><td colSpan={5} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
                  : a.schemes.length === 0 ? <tr><td colSpan={5} className="text-center py-8 text-base-content/40">暂无方案</td></tr>
                  : a.schemes.map(s => <tr key={s.id}><td>{s.id}</td><td>{s.name || `方案 #${s.id}`}</td><td><span className={`badge badge-xs ${s.status === "CONFIRMED" ? "badge-success" : s.status === "GENERATED" ? "badge-info" : "badge-warning"}`}>{s.status}</span></td><td>{s.createdAt?.replace("T"," ").substring(0,19) || "-"}</td>
                    <td><button className="btn btn-xs btn-success" disabled={s.status === "CONFIRMED"} onClick={() => a.confirmScheme(s.id)}>确认方案</button></td></tr>)}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Task dialog */}
      {a.taskDialog && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl max-h-[85vh] overflow-y-auto">
            <h3 className="font-bold text-lg mb-4">{a.taskForm.id ? "编辑排课任务" : "新增排课任务"}</h3>
            <div className="space-y-3">
              <div><label className="label pb-1"><span className="label-text">任务名称</span></label><input className="input input-bordered w-full" value={a.taskForm.name} onChange={e => a.setTaskForm({...a.taskForm, name: e.target.value})} /></div>
              
              <div className="divider text-xs">生成配置</div>
              
              <div className="grid grid-cols-4 gap-2">
                {a.WEEKS.map(w => <label key={w} className="flex items-center gap-1 text-xs"><input type="checkbox" className="checkbox checkbox-xs" checked={a.taskForm.generationConfig.allowedWeeks?.includes(w)} onChange={e => a.updateConfig("allowedWeeks", e.target.checked ? [...a.taskForm.generationConfig.allowedWeeks, w] : a.taskForm.generationConfig.allowedWeeks.filter((x:number) => x !== w))} />第{w}周</label>)}
              </div>
              <div className="flex gap-2">{a.WEEKDAYS.map(d => <label key={d.v} className="flex items-center gap-1 text-xs"><input type="checkbox" className="checkbox checkbox-xs" checked={a.taskForm.generationConfig.allowedWeekdays?.includes(d.v)} onChange={e => a.updateConfig("allowedWeekdays", e.target.checked ? [...a.taskForm.generationConfig.allowedWeekdays, d.v] : a.taskForm.generationConfig.allowedWeekdays.filter((x:number) => x !== d.v))} />{d.l}</label>)}</div>
              <div className="flex gap-2">{a.PERIODS.map(p => <label key={p} className="flex items-center gap-1 text-xs"><input type="checkbox" className="checkbox checkbox-xs" checked={a.taskForm.generationConfig.allowedPeriods?.includes(p)} onChange={e => a.updateConfig("allowedPeriods", e.target.checked ? [...a.taskForm.generationConfig.allowedPeriods, p] : a.taskForm.generationConfig.allowedPeriods.filter((x:number) => x !== p))} />第{p}节</label>)}</div>

              <div className="divider text-xs">ML 参数</div>
              <div className="grid grid-cols-4 gap-2">
                <div><label className="text-xs">方案数</label><input type="number" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.schemeCount} onChange={e => a.updateConfig("schemeCount", Number(e.target.value))} /></div>
                <div><label className="text-xs">Placement TopK</label><input type="number" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.placementTopK} onChange={e => a.updateConfig("placementTopK", Number(e.target.value))} /></div>
                <div><label className="text-xs">Solver Time(s)</label><input type="number" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.solverTimeLimitSeconds} onChange={e => a.updateConfig("solverTimeLimitSeconds", Number(e.target.value))} /></div>
                <div><label className="text-xs">Model Weight</label><input type="number" step="0.1" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.modelWeight} onChange={e => a.updateConfig("modelWeight", Number(e.target.value))} /></div>
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div><label className="text-xs">早课惩罚</label><input type="number" step="0.01" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.earlyPeriodPenalty} onChange={e => a.updateConfig("earlyPeriodPenalty", Number(e.target.value))} /></div>
                <div><label className="text-xs">晚课惩罚</label><input type="number" step="0.01" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.latePeriodPenalty} onChange={e => a.updateConfig("latePeriodPenalty", Number(e.target.value))} /></div>
                <div><label className="text-xs">周末惩罚</label><input type="number" step="0.01" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.weekendPenalty} onChange={e => a.updateConfig("weekendPenalty", Number(e.target.value))} /></div>
                <div><label className="text-xs">教师画像权重</label><input type="number" className="input input-bordered input-sm w-full" value={a.taskForm.generationConfig.teacherProfilePenaltyScale} onChange={e => a.updateConfig("teacherProfilePenaltyScale", Number(e.target.value))} /></div>
              </div>
            </div>
            <div className="modal-action">
              <button className="btn btn-ghost btn-sm" onClick={() => a.setTaskDialog(false)}>取消</button>
              <button className="btn btn-primary btn-sm" disabled={a.saving} onClick={a.saveTask}>{a.saving ? <span className="loading loading-spinner loading-xs" /> : "保存"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
