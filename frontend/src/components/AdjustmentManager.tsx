import { useAdjustment } from "../hooks/useAdjustment";

export default function AdjustmentManager() {
  const a = useAdjustment();

  return (
    <div>
      <h2 className="mb-4">调课处理</h2>

      <div className="flex gap-2 mb-4">
        {["PENDING","APPROVED","REJECTED",""].map(s => (
          <button key={s} className={`btn btn-sm ${a.statusFilter === s ? "btn-active" : ""}`} onClick={() => a.setStatusFilter(s)}>
            {s === "PENDING" ? "待处理" : s === "APPROVED" ? "已通过" : s === "REJECTED" ? "已拒绝" : "全部"}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead><tr><th>ID</th><th>调课原因</th><th>调课倾向</th><th>状态</th><th>申请时间</th><th>操作</th></tr></thead>
          <tbody>
            {a.loading ? <tr><td colSpan={6} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : a.requests.length === 0 ? <tr><td colSpan={6} className="text-center py-8 text-base-content/40">暂无调课申请</td></tr>
            : a.requests.map(r => <tr key={r.id}><td>{r.id}</td><td className="max-w-[150px] truncate">{r.reason}</td><td className="max-w-[150px] truncate">{r.preferredTimeText}</td><td><span className={`badge badge-xs ${r.status === "PENDING" ? "badge-warning" : r.status === "APPROVED" ? "badge-success" : "badge-error"}`}>{r.status}</span></td><td>{r.createdAt?.replace("T"," ").substring(0,19) || "-"}</td>
              <td><div className="flex gap-1">{r.status === "PENDING" ? <><button className="btn btn-xs btn-primary" onClick={() => a.openTimetable(r)}>调课</button><button className="btn btn-xs btn-ghost text-error" onClick={() => a.rejectRequest(r)}>拒绝</button></> : <span className="text-base-content/40 text-xs">—</span>}</div></td>
            </tr>)}
          </tbody>
        </table>
      </div>

      {/* Timetable overlay */}
      {a.timetableVisible && (
        <div className="modal modal-open">
          <div className="modal-box max-w-5xl max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-lg">调课 — 拖拽标黄片段到目标位置</h3>
              <button className="btn btn-sm btn-ghost" onClick={() => a.setTimetableVisible(false)}>关闭</button>
            </div>
            <div className="flex items-center gap-2 mb-4">
              <button className="btn btn-xs" disabled={a.currentWeek <= 1} onClick={() => a.setCurrentWeek(a.currentWeek - 1)}>‹ 上一周</button>
              <select className="select select-bordered select-xs w-28" value={a.currentWeek} onChange={e => a.setCurrentWeek(Number(e.target.value))}>{a.allWeeks.map(w => <option key={w} value={w}>第 {w} 周</option>)}</select>
              <button className="btn btn-xs" disabled={a.currentWeek >= 18} onClick={() => a.setCurrentWeek(a.currentWeek + 1)}>下一周 ›</button>
              {a.pendingMove && <><button className="btn btn-success btn-xs ml-auto" disabled={a.savingMove || !a.pendingMove.targetTimeSlotId} onClick={a.saveMove}>{a.savingMove ? <span className="loading loading-spinner loading-xs" /> : "确认移动"}</button><button className="btn btn-ghost btn-xs" onClick={() => a.setPendingMove(null)}>取消</button></>}
            </div>
            <div className="overflow-x-auto"><table className="table table-sm border-collapse"><thead><tr><th className="text-center bg-base-200 w-[60px]">节次</th>{a.DAYS.map(d => <th key={d} className="text-center bg-base-200 min-w-[100px]">{d}</th>)}</tr></thead><tbody>
              {[1,2,3,4,5].map(period => <tr key={period}><td className="text-center font-medium bg-base-200">第{period}节</td>
                {[1,2,3,4,5,6,7].map(day => {
                  const items = a.itemsAtSlot(day, period);
                  return <td key={day} className="p-1 align-top min-h-[60px] border border-base-300">
                    {items.map(item => <div key={item.id} className={`px-1 py-0.5 rounded text-xs mb-0.5 cursor-pointer ${a.isAdjustTarget(item) ? "bg-warning/30 ring-2 ring-warning" : "bg-primary/10 text-primary"}`} onClick={() => a.onSlotClick(item)}>
                      <div className="font-semibold">{item.courseName}</div><div className="text-base-content/60">{item.classroomName} · {item.teacherName}</div></div>)}
                    {items.length === 0 && <div className="text-center text-base-content/20 text-xs leading-[60px]">空</div>}
                  </td>;
                })}
              </tr>)}
            </tbody></table></div>
          </div>
        </div>
      )}
    </div>
  );
}
