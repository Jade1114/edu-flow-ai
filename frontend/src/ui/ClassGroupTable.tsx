import type { ClassGroup } from "../hooks/useClassGroups";
import BatchActionBar from "./BatchActionBar";

interface Props {
  groups: ClassGroup[];
  loading: boolean;
  search: string;
  onSearchChange: (v: string) => void;
  gradeFilter: string;
  majorFilter: string;
  departmentFilter: string;
  gradeOptions: string[];
  majorOptions: string[];
  departmentOptions: string[];
  onGradeFilterChange: (v: string) => void;
  onMajorFilterChange: (v: string) => void;
  onDepartmentFilterChange: (v: string) => void;
  hasFilter: boolean;
  onResetFilters: () => void;
  page: number;
  pageSize: number;
  total: number;
  totalStudents: number;
  onPageChange: (v: number) => void;
  onPageSizeChange: (v: number) => void;
  deleting: number | null;
  onEdit: (row: ClassGroup) => void;
  onDelete: (id: number) => void;
  onAdd: () => void;
  batch: any;
}

export default function ClassGroupTable({
  groups,
  loading,
  search,
  onSearchChange,
  gradeFilter,
  majorFilter,
  departmentFilter,
  gradeOptions,
  majorOptions,
  departmentOptions,
  onGradeFilterChange,
  onMajorFilterChange,
  onDepartmentFilterChange,
  hasFilter,
  onResetFilters,
  page,
  pageSize,
  total,
  totalStudents,
  onPageChange,
  onPageSizeChange,
  deleting,
  onEdit,
  onDelete,
  onAdd,
  batch,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">班级管理</h3>
          <p className="text-xs text-base-content/50">维护排课基础班级数据，支持按年级、专业、院系过滤。</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={onAdd}>新增班级</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3 p-3 rounded-lg border border-base-300 bg-base-100">
        <input type="text" placeholder="搜索名称 / 专业 / 院系 / 年级" className="input input-bordered input-sm" value={search} onChange={e => onSearchChange(e.target.value)} />
        <select className="select select-bordered select-sm" value={gradeFilter} onChange={e => onGradeFilterChange(e.target.value)}>
          <option value="">全部年级</option>
          {gradeOptions.map(option => <option key={option} value={option}>{option}</option>)}
        </select>
        <select className="select select-bordered select-sm" value={majorFilter} onChange={e => onMajorFilterChange(e.target.value)}>
          <option value="">全部专业</option>
          {majorOptions.map(option => <option key={option} value={option}>{option}</option>)}
        </select>
        <select className="select select-bordered select-sm" value={departmentFilter} onChange={e => onDepartmentFilterChange(e.target.value)}>
          <option value="">全部院系</option>
          {departmentOptions.map(option => <option key={option} value={option}>{option}</option>)}
        </select>
        <button className="btn btn-outline btn-sm" disabled={!hasFilter} onClick={onResetFilters}>清空筛选</button>
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-base-content/60">
        <span className="badge badge-ghost">班级 {total} 个</span>
        <span className="badge badge-ghost">学生 {totalStudents} 人</span>
        <span className="badge badge-ghost">当前页 {groups.length} 条</span>
      </div>
      <BatchActionBar label="班级" selectedCount={batch.selectedCount} filteredCount={total} busy={batch.batchBusy} disableSupported={false} onSelectFiltered={batch.selectFiltered} onClearSelection={batch.clearSelection} onDelete={batch.batchDelete} />

      <div className="overflow-x-auto rounded-lg border border-base-300 bg-base-100">
        <table className="table table-zebra table-sm">
          <thead><tr><th><input type="checkbox" className="checkbox checkbox-xs" checked={batch.pageSelected} onChange={batch.togglePageSelected} title={batch.pageIndeterminate ? "当前页已部分选择" : "选择当前页"} /></th><th>班级名称</th><th>专业</th><th>院系</th><th>年级</th><th>人数</th><th className="text-right">操作</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={7} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : groups.length === 0 ? <tr><td colSpan={7} className="text-center py-8 text-base-content/40">暂无班级数据</td></tr>
            : groups.map(g => (
              <tr key={g.id}>
                <td><input type="checkbox" className="checkbox checkbox-xs" checked={g.id !== null && batch.selectedIds.includes(g.id)} onChange={() => g.id !== null && batch.toggleSelected(g.id)} /></td>
                <td className="font-medium">{g.name}</td>
                <td>{g.major || <span className="text-base-content/30">-</span>}</td>
                <td>{g.department || <span className="text-base-content/30">-</span>}</td>
                <td><span className="badge badge-outline badge-sm">{g.grade || "-"}</span></td>
                <td>{g.studentCount}</td>
                <td>
                  <div className="flex justify-end gap-1">
                    <button className="btn btn-xs btn-ghost" onClick={() => onEdit(g)}>编辑</button>
                    <button className="btn btn-xs btn-ghost text-error" disabled={deleting === g.id} onClick={() => g.id !== null && onDelete(g.id)}>
                      {deleting === g.id ? <span className="loading loading-spinner loading-xs" /> : "删除"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
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
