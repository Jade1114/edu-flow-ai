import { useTimetable } from "../hooks/useTimetable";
import TimetableTable from "../ui/TimetableTable";
import TimetableGrid from "../ui/TimetableGrid";

export default function TimetableManager() {
  const t = useTimetable();

  return (
    <div>
      {/* Filters */}
      <div className="card bg-base-100 shadow-sm mb-4">
        <div className="card-body p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div><label className="label pb-1 text-xs">教师ID</label><input className="input input-bordered input-sm w-24" value={t.filters.teacherId} onChange={e => t.setFilters({...t.filters, teacherId: e.target.value})} /></div>
            <div><label className="label pb-1 text-xs">班级ID</label><input className="input input-bordered input-sm w-24" value={t.filters.classGroupId} onChange={e => t.setFilters({...t.filters, classGroupId: e.target.value})} /></div>
            <div><label className="label pb-1 text-xs">课程ID</label><input className="input input-bordered input-sm w-24" value={t.filters.courseId} onChange={e => t.setFilters({...t.filters, courseId: e.target.value})} /></div>
            <div><label className="label pb-1 text-xs">周次</label><input className="input input-bordered input-sm w-20" value={t.filters.weekNumber} onChange={e => t.setFilters({...t.filters, weekNumber: e.target.value})} /></div>
            <div><label className="label pb-1 text-xs">星期</label><input className="input input-bordered input-sm w-20" value={t.filters.dayOfWeek} onChange={e => t.setFilters({...t.filters, dayOfWeek: e.target.value})} /></div>
            <button className="btn btn-primary btn-sm" onClick={t.loadAssignments}>查询</button>
          </div>
        </div>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-3 mb-4">
        <div className="join">
          <button className={`join-item btn btn-sm ${t.viewMode === "table" ? "btn-active" : ""}`} onClick={() => t.setViewMode("table")}>表格视图</button>
          <button className={`join-item btn btn-sm ${t.viewMode === "grid" ? "btn-active" : ""}`} onClick={() => t.setViewMode("grid")}>课程表视图</button>
        </div>
        <span className="text-sm text-base-content/50">共 {t.assignments.length} 条记录</span>
      </div>

      {t.viewMode === "table" && <TimetableTable assignments={t.assignments} loading={t.loading} />}
      {t.viewMode === "grid" && (
        <TimetableGrid loading={t.loading} currentWeek={t.currentWeek} allWeeks={t.allWeeks}
          weekItems={t.weekItems} dayNames={t.dayNames} itemsAtSlot={t.itemsAtSlot} onWeekChange={t.setCurrentWeek} />
      )}
    </div>
  );
}
