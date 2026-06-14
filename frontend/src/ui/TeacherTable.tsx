import type { Teacher } from "../hooks/useTeachers";
import BatchActionBar from "./BatchActionBar";

interface Props {
  teachers: Teacher[]; loading: boolean; search: string;
  onSearchChange: (v: string) => void;
  statusFilter: string; onStatusFilterChange: (v: string) => void;
  page: number; pageSize: number; total: number;
  onPageChange: (v: number) => void; onPageSizeChange: (v: number) => void;
  deleting: number | null;
  onEdit: (row: Teacher) => void; onDelete: (id: number) => void; onAdd: () => void;
  batch: any;
}

export default function TeacherTable({ teachers, loading, search, onSearchChange, statusFilter, onStatusFilterChange, page, pageSize, total, onPageChange, onPageSizeChange, deleting, onEdit, onDelete, onAdd, batch }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 mb-4">
        <button className="btn btn-primary btn-sm" onClick={onAdd}>新增教师</button>
        <select className="select select-bordered select-sm w-28" value={statusFilter} onChange={e => onStatusFilterChange(e.target.value)}>
          <option value="">全部状态</option><option value="ACTIVE">启用</option><option value="INACTIVE">停用</option>
        </select>
        <input type="text" placeholder="搜索工号、姓名和部门" className="input input-bordered input-sm w-64" value={search} onChange={e => onSearchChange(e.target.value)} />
      </div>
      <BatchActionBar label="教师" selectedCount={batch.selectedCount} filteredCount={total} busy={batch.batchBusy} onSelectFiltered={batch.selectFiltered} onClearSelection={batch.clearSelection} onDisable={batch.batchDisable} onDelete={batch.batchDelete} />
      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead><tr><th><input type="checkbox" className="checkbox checkbox-xs" checked={batch.pageSelected} onChange={batch.togglePageSelected} title={batch.pageIndeterminate ? "当前页已部分选择" : "选择当前页"} /></th><th>工号</th><th>姓名</th><th>部门</th><th>职称</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={8} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : teachers.length === 0 ? <tr><td colSpan={8} className="text-center py-8 text-base-content/40">暂无教师数据</td></tr>
            : teachers.map(t => (
              <tr key={t.id}>
                <td><input type="checkbox" className="checkbox checkbox-xs" checked={t.id !== null && batch.selectedIds.includes(t.id)} onChange={() => t.id !== null && batch.toggleSelected(t.id)} /></td>
                <td>{t.employeeNo}</td><td>{t.name}</td><td>{t.department}</td><td>{t.title}</td>
                <td><span className={`badge badge-xs ${t.role === "ADMIN" ? "badge-primary" : "badge-ghost"}`}>{t.role === "ADMIN" ? "管理员" : "教师"}</span></td>
                <td><span className={`badge badge-xs ${t.status === "ACTIVE" ? "badge-success" : "badge-ghost"}`}>{t.status === "ACTIVE" ? "启用" : "停用"}</span></td>
                <td><div className="flex gap-1">
                  <button className="btn btn-xs btn-ghost" onClick={() => onEdit(t)}>编辑</button>
                  <button className="btn btn-xs btn-ghost text-error" disabled={deleting === t.id} onClick={() => t.id !== null && onDelete(t.id)}>
                    {deleting === t.id ? <span className="loading loading-spinner loading-xs" /> : "删除"}
                  </button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-2 text-sm text-base-content/60">
          <span>共 {total} 条</span>
          <select className="select select-bordered select-xs w-20" value={pageSize} onChange={e => onPageSizeChange(Number(e.target.value))}>
            <option value="5">5</option><option value="10">10</option><option value="20">20</option><option value="50">50</option>
          </select><span>条/页</span>
        </div>
        <div className="join">
          <button className="join-item btn btn-xs" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
          <span className="join-item btn btn-xs no-animation">{page} / {totalPages}</span>
          <button className="join-item btn btn-xs" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
        </div>
      </div>
    </div>
  );
}
