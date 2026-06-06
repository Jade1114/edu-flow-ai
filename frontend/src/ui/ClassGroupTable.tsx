import type { ClassGroup } from "../hooks/useClassGroups";

interface Props {
  groups: ClassGroup[]; loading: boolean; search: string;
  onSearchChange: (v: string) => void;
  page: number; pageSize: number; total: number;
  onPageChange: (v: number) => void; onPageSizeChange: (v: number) => void;
  deleting: number | null;
  onEdit: (row: ClassGroup) => void; onDelete: (id: number) => void; onAdd: () => void;
}

export default function ClassGroupTable({ groups, loading, search, onSearchChange, page, pageSize, total, onPageChange, onPageSizeChange, deleting, onEdit, onDelete, onAdd }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <button className="btn btn-primary btn-sm" onClick={onAdd}>新增班级</button>
        <input type="text" placeholder="搜索班级名称或专业" className="input input-bordered input-sm w-64" value={search} onChange={e => onSearchChange(e.target.value)} />
      </div>
      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead><tr><th>班级名称</th><th>专业</th><th>院系</th><th>年级</th><th>人数</th><th>操作</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : groups.length === 0 ? <tr><td colSpan={6} className="text-center py-8 text-base-content/40">暂无班级数据</td></tr>
            : groups.map(g => (
              <tr key={g.id}>
                <td>{g.name}</td><td>{g.major}</td><td>{g.department}</td><td>{g.grade}</td><td>{g.studentCount}</td>
                <td><div className="flex gap-1">
                  <button className="btn btn-xs btn-ghost" onClick={() => onEdit(g)}>编辑</button>
                  <button className="btn btn-xs btn-ghost text-error" disabled={deleting === g.id} onClick={() => g.id !== null && onDelete(g.id)}>
                    {deleting === g.id ? <span className="loading loading-spinner loading-xs" /> : "删除"}
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
