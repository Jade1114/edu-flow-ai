import type { Course } from "../hooks/useCourses";
import BatchActionBar from "./BatchActionBar";

interface CourseTableProps {
  courses: Course[];
  loading: boolean;
  search: string;
  onSearchChange: (v: string) => void;
  statusFilter: string;
  onStatusFilterChange: (v: string) => void;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (v: number) => void;
  onPageSizeChange: (v: number) => void;
  deleting: number | null;
  onEdit: (row: Course) => void;
  onDelete: (id: number) => void;
  onAdd: () => void;
  batch: any;
}

export default function CourseTable({
  courses,
  loading,
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  deleting,
  onEdit,
  onDelete,
  onAdd,
  batch,
}: CourseTableProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 mb-4">
        <button className="btn btn-primary btn-sm" onClick={onAdd}>
          新增课程
        </button>
        <select className="select select-bordered select-sm w-28" value={statusFilter} onChange={(e) => onStatusFilterChange(e.target.value)}>
          <option value="">全部状态</option>
          <option value="ACTIVE">启用</option>
          <option value="INACTIVE">停用</option>
        </select>
        <input
          type="text"
          placeholder="搜索课程名称或代码"
          className="input input-bordered input-sm w-64"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
      <BatchActionBar label="课程" selectedCount={batch.selectedCount} filteredCount={total} busy={batch.batchBusy} onSelectFiltered={batch.selectFiltered} onClearSelection={batch.clearSelection} onDisable={batch.batchDisable} onDelete={batch.batchDelete} />

      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead>
            <tr>
              <th>
                <input type="checkbox" className="checkbox checkbox-xs" checked={batch.pageSelected} onChange={batch.togglePageSelected} title={batch.pageIndeterminate ? "当前页已部分选择" : "选择当前页"} />
              </th>
              <th>课程名称</th>
              <th>课程代码</th>
              <th>学分</th>
              <th>课程类型</th>
              <th>教室类型</th>
              <th>学时</th>
              <th>描述</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="text-center py-8">
                  <span className="loading loading-spinner" />
                </td>
              </tr>
            ) : courses.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-8 text-base-content/40">
                  暂无课程数据
                </td>
              </tr>
            ) : (
              courses.map((c) => (
                <tr key={c.id}>
                  <td>
                    <input type="checkbox" className="checkbox checkbox-xs" checked={c.id !== null && batch.selectedIds.includes(c.id)} onChange={() => c.id !== null && batch.toggleSelected(c.id)} />
                  </td>
                  <td>{c.name}</td>
                  <td>{c.code}</td>
                  <td>{c.credits}</td>
                  <td>
                    <span
                      className={`badge badge-xs ${
                        c.courseType === "理论课"
                          ? "badge-primary"
                          : c.courseType === "上机课"
                            ? "badge-success"
                            : "badge-warning"
                      }`}
                    >
                      {c.courseType || "-"}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-xs badge-ghost">
                      {c.requiredRoomType || "-"}
                    </span>
                  </td>
                  <td>{c.requiredHours}</td>
                  <td className="max-w-[120px] truncate">{c.description || "-"}</td>
                  <td>
                    <span
                      className={`badge badge-xs ${
                        c.status === "ACTIVE" ? "badge-success" : "badge-ghost"
                      }`}
                    >
                      {c.status === "ACTIVE" ? "启用" : "停用"}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <button
                        className="btn btn-xs btn-ghost"
                        onClick={() => onEdit(c)}
                      >
                        编辑
                      </button>
                      <button
                        className="btn btn-xs btn-ghost text-error"
                        disabled={deleting === c.id}
                        onClick={() => c.id !== null && onDelete(c.id)}
                      >
                        {deleting === c.id ? (
                          <span className="loading loading-spinner loading-xs" />
                        ) : (
                          "删除"
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-2 text-sm text-base-content/60">
          <span>共 {total} 条</span>
          <select
            className="select select-bordered select-xs w-20"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
          >
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
          <span>条/页</span>
        </div>
        <div className="join">
          <button
            className="join-item btn btn-xs"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            上一页
          </button>
          <span className="join-item btn btn-xs no-animation">
            {page} / {totalPages}
          </span>
          <button
            className="join-item btn btn-xs"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
