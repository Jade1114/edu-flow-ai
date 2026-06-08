import { useState, useMemo, useEffect } from "react";
import { useAllocation, type SchemeItem } from "../hooks/useAllocation";

// ── Rainbow color assignment ──────────────────────────
const RAINBOW_HUES = [
  0, 20, 45, 80, 140, 175, 200, 230, 260, 290, 320, 345,
];
function taskKey(item: SchemeItem) {
  return `${item.courseName ?? ""}|${item.teacherName ?? ""}|${item.classGroupName ?? ""}`;
}
function buildHueMap(items: SchemeItem[]) {
  const keys = [...new Set(items.map(taskKey))].sort();
  const m = new Map<string, number>();
  keys.forEach((k, i) => m.set(k, RAINBOW_HUES[i % RAINBOW_HUES.length]));
  return m;
}

function SchemeTimetable({
  items,
  selectedConflictId,
  onConflictClick,
}: {
  items: SchemeItem[];
  selectedConflictId?: number | null;
  onConflictClick?: (item: SchemeItem) => void;
}) {
  const [week, setWeek] = useState(0);
  const allWeeks = [...new Set(items.map(i => i.weekNumber))].sort((a, b) => a - b);
  const currentWeek = week || allWeeks[0] || 0;
  const weekItems = items.filter(i => i.weekNumber === currentWeek);

  const hueMap = useMemo(() => buildHueMap(items), [items]);

  const days = [1,2,3,4,5,6,7];
  const dayLabels = ["周一","周二","周三","周四","周五","周六","周日"];
  const periods = [1,2,3,4,5];
  const periodLabels = ["第1节","第2节","第3节","第4节","第5节"];

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
          <span className="text-xs text-base-content/40 font-medium">周次</span>
          <div className="join">
            {allWeeks.map(w => (
              <button key={w}
                className={`join-item btn btn-xs min-w-8 ${w === currentWeek ? "btn-active btn-primary text-primary-content" : "btn-ghost text-base-content/60"}`}
                onClick={() => setWeek(w)}>{w}</button>
            ))}
          </div>
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-base-300">
        <table className="table table-sm w-full">
          <thead>
            <tr className="bg-base-200/50">
              <th className="w-14 text-xs font-medium text-base-content/50 text-center">节次</th>
              {days.map((d, i) => (
                <th key={d} className={`text-center text-xs font-medium w-28 px-1 ${i >= 5 ? "text-warning/60" : "text-base-content/50"}`}>
                  {dayLabels[d-1]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map(p => (
              <tr key={p} className="border-t border-base-200/50">
                <td className="text-xs text-base-content/40 text-center font-mono px-1 py-0.5 align-top leading-[60px]">{periodLabels[p-1]}</td>
                {days.map(d => {
                  const slotItems = map.get(`${d}-${p}`);
                  return (
                    <td key={d} className="p-0.5 align-top min-h-[60px]">
                      {slotItems?.map(item => {
                        const hue = hueMap.get(taskKey(item)) ?? 0;
                        return (
                          <div key={item.id}
                            className={`text-[11px] leading-snug mb-0.5 p-1.5 rounded-md border-l-[3px] transition-all ${
                              selectedConflictId === item.id ? "ring-2 ring-error ring-offset-1" : ""
                            } ${
                              item.valid !== false ? "text-base-content" : "text-error cursor-pointer hover:brightness-110"
                            }`}
                            style={{
                              borderLeftColor: item.valid !== false ? `hsl(${hue}, 65%, 50%)` : undefined,
                              backgroundColor: item.valid !== false
                                ? `hsla(${hue}, 65%, 50%, 0.1)`
                                : undefined,
                            }}
                            onClick={() => item.valid === false && onConflictClick?.(item)}
                            title={item.conflictMessage || ""}>
                            {item.valid === false && (
                              <div className="flex items-center gap-1 mb-0.5">
                                <span className="inline-block w-1.5 h-1.5 rounded-full bg-error animate-pulse" />
                                <span className="text-[9px] uppercase tracking-wider font-semibold">冲突</span>
                              </div>
                            )}
                            <div className="font-semibold truncate" style={{ color: `hsl(${hue}, 65%, 60%)` }}>
                              {item.courseName || "-"}
                            </div>
                            <div className="text-[10px] text-base-content/60 truncate">{item.classGroupName || "-"}</div>
                            <div className="text-[10px] text-base-content/40 truncate">{item.classroomName || "-"} · {item.teacherName || "-"}</div>
                          </div>
                        );
                      })}
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
  const hueMap = useMemo(() => a.schemeItems.length ? buildHueMap(a.schemeItems) : new Map(), [a.schemeItems]);
  const [selectedConflictId, setSelectedConflictId] = useState<number | null>(null);

  const conflictItems = useMemo(() => a.schemeItems.filter(i => i.valid === false), [a.schemeItems]);

  const dayLabels = ["周日","周一","周二","周三","周四","周五","周六"];
  const periodLabels = ["第1节","第2节","第3节","第4节","第5节","第6节","第7节","第8节"];

  // Reset conflict selection when scheme items change
  useEffect(() => { setSelectedConflictId(null); }, [a.schemeItems]);

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
                <button className="btn btn-info btn-sm" disabled={a.generating || !a.selectedTask} onClick={a.generateSchemes}>
                  {a.generating ? <><span className="loading loading-spinner loading-xs" /> V3.5 排课中...</> : "V3.5 模板排课"}
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

          {/* Scheme detail — modal */}
          {a.detailScheme && (
            <div className="modal modal-open" onClick={() => a.setDetailScheme(null)}>
              <div className="modal-box max-w-6xl max-h-[92vh] overflow-y-hidden flex flex-col p-0" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-base-300 shrink-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-lg tracking-tight">
                      {a.detailScheme.name || `方案 #${a.detailScheme.id}`}
                    </h3>
                    {a.detailScheme.schemeScore != null && (
                      <span className="badge badge-sm badge-outline text-info font-mono">
                        {a.detailScheme.schemeScore.toFixed(4)}
                      </span>
                    )}
                    {conflictItems.length > 0 && (
                      <span className="badge badge-sm badge-error gap-1">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                        {conflictItems.length} 个冲突
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-base-content/40 font-medium">{a.schemeItems.length} 条排课记录</span>
                    <button className="btn btn-xs btn-ghost btn-square text-base-content/50 hover:text-base-content" onClick={() => a.setDetailScheme(null)}>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" /></svg>
                    </button>
                  </div>
                </div>
                {/* Body */}
                <div className="flex-1 overflow-y-auto px-6 py-4">
                  {a.schemeItemsLoading ? (
                    <div className="flex items-center justify-center py-24">
                      <span className="loading loading-spinner loading-lg text-primary" />
                    </div>
                  ) : a.schemeItems.length === 0 ? (
                    <div className="flex items-center justify-center py-24 text-base-content/30 font-medium">暂无排课明细数据</div>
                  ) : (
                    <div className="space-y-5">
                      <SchemeTimetable items={a.schemeItems} selectedConflictId={selectedConflictId} onConflictClick={(item) => setSelectedConflictId(selectedConflictId === item.id ? null : item.id)} />
                      <details className="collapse collapse-arrow border border-base-300 rounded-lg bg-base-100">
                        <summary className="collapse-title text-sm font-medium text-base-content/70">列表视图（{a.schemeItems.length} 条）</summary>
                        <div className="collapse-content p-0">
                          <div className="overflow-x-auto">
                            <table className="table table-sm">
                              <thead>
                                <tr className="text-xs text-base-content/50 uppercase tracking-wider">
                                  <th className="font-medium w-2"></th>
                                  <th className="font-medium">周次</th>
                                  <th className="font-medium">星期</th>
                                  <th className="font-medium">节次</th>
                                  <th className="font-medium">课程</th>
                                  <th className="font-medium">教师</th>
                                  <th className="font-medium">班级</th>
                                  <th className="font-medium">教室</th>
                                  <th className="font-medium">评分</th>
                                </tr>
                              </thead>
                              <tbody>
                                {a.schemeItems.map(item => {
                                const hue = hueMap.get(taskKey(item)) ?? 0;
                                return (
                                  <tr key={item.id}
                                    className={`text-sm transition-colors ${item.valid === false ? "bg-error/5" : ""}`}>
                                    <td className="w-3 px-0">
                                      {item.valid !== false && (
                                        <span className="inline-block w-full h-full min-h-[1.5rem]" style={{ backgroundColor: `hsl(${hue}, 65%, 50%)` }}>&nbsp;</span>
                                      )}
                                    </td>
                                    <td className="font-mono text-xs">{item.weekNumber}</td>
                                    <td>{a.dayNames[item.dayOfWeek] || item.dayOfWeek}</td>
                                    <td className="font-mono text-xs">第{item.periodIndex}节</td>
                                    <td className="font-medium">{item.courseName || "-"}</td>
                                    <td className="text-base-content/70">{item.teacherName || "-"}</td>
                                    <td className="text-base-content/70">{item.classGroupName || "-"}</td>
                                    <td className="text-base-content/70 font-mono text-xs">{item.classroomName || "-"}</td>
                                    <td className="font-mono text-xs text-right">{item.teacherProfileScore != null ? item.teacherProfileScore.toFixed(2) : "-"}</td>
                                  </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </details>

                      {/* Conflict details */}
                      {conflictItems.length > 0 && (
                        <details className="collapse collapse-arrow border border-error/30 rounded-lg bg-error/[0.03]" open>
                          <summary className="collapse-title text-sm font-medium text-error flex items-center gap-2">
                            <span className="inline-block w-2 h-2 rounded-full bg-error" />
                            冲突详情（{conflictItems.length} 项）
                          </summary>
                          <div className="collapse-content p-0">
                            <div className="divide-y divide-error/10">
                              {conflictItems.map(item => {
                                const isSelected = selectedConflictId === item.id;
                                const hue = hueMap.get(taskKey(item)) ?? 0;
                                return (
                                  <div key={item.id}
                                    className={`px-4 py-3 flex items-start gap-3 cursor-pointer transition-colors ${isSelected ? "bg-error/[0.08]" : "hover:bg-error/[0.04]"}`}
                                    onClick={() => setSelectedConflictId(isSelected ? null : item.id)}>
                                    {/* Color indicator */}
                                    <div className="w-1 h-full min-h-[3rem] shrink-0 rounded-full mt-0.5"
                                      style={{ backgroundColor: `hsl(${hue}, 65%, 50%)` }} />
                                    {/* Content */}
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 text-sm flex-wrap">
                                        <span className="font-semibold">{item.courseName || "-"}</span>
                                        <span className="text-base-content/50">·</span>
                                        <span className="text-base-content/60 text-xs">{item.teacherName || "-"}</span>
                                        <span className="text-base-content/50">·</span>
                                        <span className="text-base-content/60 text-xs">{item.classGroupName || "-"}</span>
                                      </div>
                                      <div className="text-xs text-base-content/40 mt-0.5">
                                        第{item.weekNumber}周 {dayLabels[item.dayOfWeek] || item.dayOfWeek} {periodLabels[item.periodIndex - 1] || `第${item.periodIndex}节`} · {item.classroomName || "-"}
                                      </div>
                                      <div className="flex items-start gap-1.5 mt-2 p-2 rounded bg-error/[0.06] text-xs text-error">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0 mt-0.5"><path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clipRule="evenodd" /></svg>
                                        <span>{item.conflictMessage || "未知冲突"}</span>
                                      </div>
                                    </div>
                                    {/* Selected indicator */}
                                    {isSelected && (
                                      <span className="text-xs text-error font-medium shrink-0">查看中</span>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </details>
                      )}

                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* V3.5 Template section */}
      {a.selectedTask && a.v35Templates.length > 0 && (
        <div className="card bg-base-100 shadow-sm border border-info/20">
          <div className="card-body p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold text-info">V3.5 模板排课结果</span>
              <button className="btn btn-ghost btn-xs" onClick={() => a.loadV35Templates(a.selectedTask!.id)}>刷新</button>
            </div>

            {/* Template list */}
            <div className="flex flex-wrap gap-2 mb-3">
              {a.v35Templates.map((t: any) => (
                <div key={t.templateCode} className="badge badge-info badge-outline gap-1 p-3">
                  <span className="font-mono text-xs">{t.templateCode}</span>
                  <span className="text-[10px] opacity-60">{t.fragmentCount} 片段 · {t.taskCount} 任务</span>
                </div>
              ))}
            </div>

            {/* Week -> template mapping */}
            <details className="collapse collapse-arrow border border-base-300 rounded-lg">
              <summary className="collapse-title text-sm font-medium text-base-content/70 min-h-0 py-2">
                周模板映射（{a.v35TemplateWeeks.length} 周）
              </summary>
              <div className="collapse-content p-0">
                <div className="flex flex-wrap gap-1.5 p-2">
                  {a.v35TemplateWeeks.map((w: any) => (
                    <button
                      key={w.weekNumber}
                      className={`btn btn-xs ${a.v35SelectedWeek === w.weekNumber ? "btn-info" : "btn-ghost"} ${w.templateCode === "cover_v1_template_2" ? "border-dashed" : ""}`}
                      onClick={() => a.loadV35WeekTimetable(a.selectedTask!.id, w.weekNumber)}
                    >
                      第{w.weekNumber}周
                      <span className="text-[9px] opacity-50 ml-0.5">{w.templateCode === "cover_v1_template_1" ? "T1" : "T2"}</span>
                    </button>
                  ))}
                </div>
              </div>
            </details>

            {/* Week timetable */}
            {a.v35SelectedWeek && a.v35WeekTimetable.length > 0 && (
              <div className="mt-3 overflow-x-auto max-h-64 overflow-y-auto">
                <table className="table table-xs table-zebra">
                  <thead>
                    <tr>
                      <th>周</th>
                      <th>星期</th>
                      <th>课段</th>
                      <th>教室</th>
                      <th>班级</th>
                      <th>课程</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.v35WeekTimetable.slice(0, 100).map((e: any, i: number) => (
                      <tr key={i}>
                        <td>{e.weekNumber}</td>
                        <td>{["","周一","周二","周三","周四","周五","周六","周日"][e.dayOfWeek] || e.dayOfWeek}</td>
                        <td>{e.periodIndex}</td>
                        <td className="font-mono text-xs">{e.classroomName}</td>
                        <td className="max-w-[120px] truncate">{e.className}</td>
                        <td className="max-w-[150px] truncate">{e.courseName}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {a.v35WeekTimetable.length > 100 && (
                  <div className="text-center text-xs text-base-content/40 py-2">
                    仅显示前 100 条，共 {a.v35WeekTimetable.length} 条
                  </div>
                )}
              </div>
            )}
            {a.v35SelectedWeek && a.v35WeekTimetable.length === 0 && (
              <div className="text-center text-xs text-base-content/40 py-4">该周暂无课表数据</div>
            )}
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
