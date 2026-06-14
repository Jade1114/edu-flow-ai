import type { Classroom } from "../hooks/useClassrooms";
import BatchActionBar from "./BatchActionBar";

interface ClassroomTableProps {
  classrooms: Classroom[];
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
  onEdit: (row: Classroom) => void;
  onDelete: (id: number) => void;
  onAdd: () => void;
  batch: any;
}

export default function ClassroomTable({
  classrooms,
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
}: ClassroomTableProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 mb-4">
        <button className="btn btn-primary btn-sm" onClick={onAdd}>
          新增教室
        </button>
        <select className="select select-bordered select-sm w-28" value={statusFilter} onChange={(e) => onStatusFilterChange(e.target.value)}>
          <option value="">全部状态</option>
          <option value="ACTIVE">启用</option>
          <option value="INACTIVE">停用</option>
        </select>
        <input
          type="text"
          placeholder="搜索教室名称、类型或教学楼"
          className="input input-bordered input-sm w-64"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
      <BatchActionBar label="教室" selectedCount={batch.selectedCount} filteredCount={total} busy={batch.batchBusy} onSelectFiltered={batch.selectFiltered} onClearSelection={batch.clearSelection} onDisable={batch.batchDisable} onDelete={batch.batchDelete} />

      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead>
            <tr>
              <th>
                <input type="checkbox" className="checkbox checkbox-xs" checked={batch.pageSelected} onChange={batch.togglePageSelected} title={batch.pageIndeterminate ? "当前页已部分选择" : "选择当前页"} />
              </th>
              <th>教室名称</th>
              <th>教学楼</th>
              <th>容量</th>
              <th>类型</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-8">
                  <span className="loading loading-spinner" />
                </td>
              </tr>
            ) : classrooms.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-base-content/40">
                  暂无教室数据
                </td>
              </tr>
            ) : (
              classrooms.map((room) => (
                <tr key={room.id}>
                  <td>
                    <input type="checkbox" className="checkbox checkbox-xs" checked={room.id !== null && batch.selectedIds.includes(room.id)} onChange={() => room.id !== null && batch.toggleSelected(room.id)} />
                  </td>
                  <td>{room.name}</td>
                  <td>{room.building}</td>
                  <td>{room.capacity}</td>
                  <td>{room.classroomType}</td>
                  <td>
                    <span
                      className={`badge badge-xs ${
                        room.status === "ACTIVE" ? "badge-success" : "badge-ghost"
                      }`}
                    >
                      {room.status === "ACTIVE" ? "启用" : "停用"}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <button
                        className="btn btn-xs btn-ghost"
                        onClick={() => onEdit(room)}
                      >
                        编辑
                      </button>
                      <button
                        className="btn btn-xs btn-ghost text-error"
                        disabled={deleting === room.id}
                        onClick={() => room.id !== null && onDelete(room.id)}
                      >
                        {deleting === room.id ? (
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
