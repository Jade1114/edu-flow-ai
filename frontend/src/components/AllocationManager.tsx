import { useState } from "react";
import { useAllocation, type SchemeItem } from "../hooks/useAllocation";

function SchemeTimetable({ items }: { items: SchemeItem[] }) {
  const [week, setWeek] = useState(0);
  const allWeeks = [...new Set(items.map(i => i.weekNumber))].sort((a, b) => a - b);
  const currentWeek = week || allWeeks[0] || 0;
  const weekItems = items.filter(i => i.weekNumber === currentWeek);

  const days = [1,2,3,4,5,6,7];
  const dayLabels = ["周一","周二","周三","周四","周五","周六","周日"];
  const periods = [1,2,3,4,5,6,7,8];
  const periodLabels = ["第1节","第2节","第3节","第4节","第5节","第6节","第7节","第8节"];

  // Group by day × period
  const map = new Map<string, SchemeItem[]>();
  for (const item of weekItems) {
    const key = `${item.dayOfWeek}-${item.periodIndex}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }

  return (
    <div>
      {/* Week selector */}
      {allWeeks.length > 1 && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-base-content/50">周次：</span>
          <div className="join">
            {allWeeks.map(w => (
              <button key={w} className={`join-item btn btn-xs ${w === currentWeek ? "btn-active btn-primary" : ""}`}
                onClick={() => setWeek(w)}>{w}</button>
            ))}
          </div>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="table table-xs table-zebra border">
          <thead>
            <tr>
              <th className="w-16">节次</th>
              {days.map(d => <th key={d} className="text-center w-28">{dayLabels[d-1]}</th>)}
            </tr>
          </thead>
          <tbody>
            {periods.map(p => (
              <tr key={p}>
                <td className="text-xs text-base-content/50">{periodLabels[p-1]}</td>
                {days.map(d => {
                  const slotItems = map.get(`${d}-${p}`);
                  return (
                    <td key={d} className="p-1 align-top min-h-[60px]">
                      {slotItems?.map(item => (
                        <div key={item.id} className={`text-[10px] leading-tight mb-1 p-1 rounded-sm border-l-2 ${item.valid !== false ? "border-l-success bg-base-200" : "border-l-error bg-red-50"}`}
                          title={item.conflictMessage || ""}>
                          <div className="font-medium truncate">{item.courseName || "-"}</div>
                          <div className="text-base-content/50 truncate">{item.teacherName || "-"}</div>
                          <div className="text-base-content/40 truncate">{item.classroomName || "-"}</div>
                        </div>
                      ))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

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
            : a.tasks.map(t => <tr key={t.id} className={a.selectedTask?.id === t.id ? "bg-primary/5" : ""}>
                <td>{t.id}</td>
                <td className="font-medium cursor-pointer hover:text-primary" onClick={() => a.selectTask(t)}>{t.name || `任务 #${t.id}`}</td>
                <td>{t.schemeCount ?? "-"}</td>
                <td><span className={`badge badge-xs ${t.status === "ACTIVE" ? "badge-success" : "badge-ghost"}`}>{t.status}</span></td>
                <td><div className="flex gap-1">
                  <button className="btn btn-xs btn-ghost" onClick={() => a.openTaskDialog(t)}>编辑</button>
                  <button className="btn btn-xs btn-ghost text-error" onClick={() => a.deleteTask(t.id)}>删除</button>
                </div></td>
              </tr>)}
          </tbody>
        </table>
      </div>

      {/* Selected task -> schemes + detail */}
      {a.selectedTask && (
        <div className="flex flex-col gap-4">
          {/* Schemes section */}
          <div className="card bg-base-100 shadow-sm">
            <div className="card-body p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="font-bold">方案列表 — {a.selectedTask.name || `任务 #${a.selectedTask.id}`}</span>
                <button className="btn btn-warning btn-sm" disabled={a.generating || !a.selectedTask} onClick={a.generateSchemes}>
                  {a.generating ? <><span className="loading loading-spinner loading-xs" /> 排课中...</> : "开始排课"}
                </button>
              </div>
              {a.generating && (
                <div className="mb-4">
                  <div className="flex items-center justify-between text-xs text-base-content/60 mb-1">
                    <span>{a.generateStatus}</span>
                    <span>{a.generateProgress}%</span>
                  </div>
                  <div className="h-2.5 rounded-full bg-base-300 overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-warning to-success transition-all duration-500" style={{ width: `${a.generateProgress}%` }} />
                  </div>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="table table-sm table-zebra">
                  <thead><tr><th>ID</th><th>方案名</th><th>评分</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
                  <tbody>
                    {a.schemesLoading ? <tr><td colSpan={6} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
                    : a.schemes.length === 0 ? <tr><td colSpan={6} className="text-center py-8 text-base-content/40">暂无方案，点击「生成排课方案」开始</td></tr>
                    : a.schemes.map(s => <tr key={s.id} className={`cursor-pointer ${a.detailScheme?.id === s.id ? "bg-primary/5" : ""}`} onClick={() => a.loadSchemeItems(s)}>
                        <td>{s.id}</td>
                        <td>{s.name || `方案 #${s.id}`}</td>
                        <td>{s.schemeScore != null ? s.schemeScore.toFixed(2) : "-"}</td>
                        <td><span className={`badge badge-xs ${s.status === "CONFIRMED" ? "badge-success" : s.status === "GENERATED" ? "badge-info" : "badge-warning"}`}>{s.status}</span></td>
                        <td>{s.createdAt?.replace("T"," ").substring(0,19) || "-"}</td>
                        <td>
                          <button className="btn btn-xs btn-success" disabled={s.status === "CONFIRMED"} onClick={(e) => { e.stopPropagation(); a.confirmScheme(s.id); }}>确认方案</button>
                        </td>
                      </tr>)}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Scheme detail */}
          {a.detailScheme && (
            <div className="card bg-base-100 shadow-sm">
              <div className="card-body p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold">方案明细 — {a.detailScheme.name || `方案 #${a.detailScheme.id}`}</span>
                  <span className="text-sm text-base-content/50">{a.schemeItems.length} 条排课记录</span>
                </div>
                {a.schemeItemsLoading ? (
                  <div className="text-center py-8"><span className="loading loading-spinner" /></div>
                ) : a.schemeItems.length === 0 ? (
                  <div className="text-center py-8 text-base-content/40">暂无明细数据</div>
                ) : (
                  <div className="space-y-4">
                    <SchemeTimetable items={a.schemeItems} />
                    <details className="collapse collapse-arrow bg-base-200">
                      <summary className="collapse-title text-sm font-medium">查看列表视图（{a.schemeItems.length} 条）</summary>
                      <div className="collapse-content p-0">
                        <div className="overflow-x-auto">
                          <table className="table table-xs table-zebra">
                            <thead><tr><th>周次</th><th>星期</th><th>节次</th><th>课程</th><th>教师</th><th>班级</th><th>教室</th><th>评分</th></tr></thead>
                            <tbody>
                              {a.schemeItems.map(item => (
                                <tr key={item.id} className={item.valid === false ? "bg-red-50" : ""}>
                                  <td>{item.weekNumber}</td>
                                  <td>{a.dayNames[item.dayOfWeek] || item.dayOfWeek}</td>
                                  <td>第{item.periodIndex}节</td>
                                  <td>{item.courseName || "-"}</td>
                                  <td>{item.teacherName || "-"}</td>
                                  <td>{item.classGroupName || "-"}</td>
                                  <td>{item.classroomName || "-"}</td>
                                  <td>{item.teacherProfileScore != null ? item.teacherProfileScore.toFixed(2) : "-"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </details>
                    {a.detailScheme.schemeScore != null && (
                      <div className="text-sm text-base-content/50 text-right">方案评分: {a.detailScheme.schemeScore.toFixed(4)}</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Task dialog */}
      {a.taskDialog && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl max-h-[85vh] overflow-y-auto">
            <h3 className="font-bold text-lg mb-4">{a.taskForm.id ? "编辑排课任务" : "新增排课任务"}</h3>
            <div className="space-y-3">
              <div><label className="label pb-1"><span className="label-text">任务名称</span></label><input className="input input-bordered w-full" value={a.taskForm.name} onChange={e => a.setTaskForm({...a.taskForm, name: e.target.value})} /></div>

              {/* Teaching task selector */}
              <div>
                <label className="label pb-1"><span className="label-text">绑定教学任务</span></label>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-base-content/40">共 {a.teachingTasks.length} 项，已选 {a.taskForm.teachingTaskIds.length} 项</span>
                  <div className="flex gap-2">
                    <button className="btn btn-ghost btn-xs" onClick={() => a.selectAllTeachingTasks(true)}>全选</button>
                    <button className="btn btn-ghost btn-xs" onClick={() => a.selectAllTeachingTasks(false)}>取消</button>
                  </div>
                </div>
                <div className="border border-base-300 rounded-lg max-h-48 overflow-y-auto p-1">
                  {a.teachingTasksLoading ? (
                    <div className="text-center py-4"><span className="loading loading-spinner loading-xs" /></div>
                  ) : a.teachingTasks.length === 0 ? (
                    <div className="text-center py-4 text-base-content/40 text-xs">暂无教学任务，请先在「教学任务」页面添加</div>
                  ) : (
                    <div className="space-y-0.5">
                      {a.teachingTasks.map(tt => {
                        const selected = a.taskForm.teachingTaskIds.includes(tt.id);
                        return (
                          <label key={tt.id} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs hover:bg-base-200 ${selected ? "bg-primary/10" : ""}`}>
                            <input type="checkbox" className="checkbox checkbox-xs" checked={selected} onChange={() => a.toggleTeachingTask(tt.id)} />
                            <span className="font-medium">{tt.courseName}</span>
                            <span className="text-base-content/40">{tt.teacherName}</span>
                            <span className="text-base-content/30 text-[10px] ml-auto truncate max-w-[120px]">{tt.classGroupNames}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
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
