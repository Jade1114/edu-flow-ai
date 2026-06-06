import { useConstraintEditor } from "../hooks/useConstraintEditor";

export default function ConstraintEditorManager() {
  const c = useConstraintEditor();

  return (
    <div className="flex flex-col gap-4">
      {/* Task selector */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">排课任务：</span>
        <select className="select select-bordered select-sm" value={c.selectedTaskId || ""} onChange={e => c.setSelectedTaskId(Number(e.target.value))}>
          {c.tasks.map(t => <option key={t.id} value={t.id}>任务 #{t.id}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" onClick={c.loadTasks}>刷新</button>
      </div>

      {/* Constraint list */}
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-bold">当前约束 ({c.constraints.length})</span>
            <button className="btn btn-primary btn-sm" onClick={c.addBlank}>添加约束</button>
          </div>
          {c.loading ? <div className="text-center py-8"><span className="loading loading-spinner" /></div>
          : c.constraints.length === 0 ? <div className="text-center py-8 text-base-content/40">暂无约束</div>
          : <div className="overflow-x-auto"><table className="table table-sm">
            <thead><tr><th>类型</th><th>目标类型</th><th>目标ID</th><th>原因</th><th>操作</th></tr></thead>
            <tbody>{c.constraints.map((ct, i) => (
              <tr key={i}>
                <td>
                  <select className="select select-bordered select-xs" value={ct.type} onChange={e => { const updated = [...c.constraints]; updated[i] = { ...ct, type: e.target.value }; c.saveAll(updated); }}>
                    <option value="HARD">HARD</option><option value="SOFT">SOFT</option>
                  </select>
                </td>
                <td><input className="input input-bordered input-xs w-24" value={ct.targetType} onChange={e => { const u = [...c.constraints]; u[i] = { ...ct, targetType: e.target.value }; c.saveAll(u); }} /></td>
                <td><input className="input input-bordered input-xs w-20" value={ct.targetId} onChange={e => { const u = [...c.constraints]; u[i] = { ...ct, targetId: e.target.value }; c.saveAll(u); }} /></td>
                <td><input className="input input-bordered input-xs w-32" value={ct.reason} onChange={e => { const u = [...c.constraints]; u[i] = { ...ct, reason: e.target.value }; c.saveAll(u); }} /></td>
                <td><button className="btn btn-ghost btn-xs text-error" onClick={() => c.removeConstraint(i)}>删除</button></td>
              </tr>
            ))}</tbody>
          </table></div>}
        </div>
      </div>

      {/* Text translation */}
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body p-4">
          <div className="font-bold mb-3">自然语言转约束</div>
          <textarea className="textarea textarea-bordered w-full" rows={3} placeholder='例如："计算机学院教师尽量排在上午"' value={c.inputText} onChange={e => c.setInputText(e.target.value)} />
          <div className="flex gap-2 mt-2">
            <button className="btn btn-primary btn-sm" disabled={c.translating} onClick={c.translateInput}>{c.translating ? <span className="loading loading-spinner loading-xs" /> : "翻译"}</button>
            {c.preview.length > 0 && <button className="btn btn-success btn-sm" onClick={c.applyConstraints}>应用 {c.preview.length} 条</button>}
            {c.preview.length > 0 && <button className="btn btn-ghost btn-sm" onClick={() => { c.setPreview([]); c.setInputText(""); }}>取消</button>}
          </div>
          {c.preview.length > 0 && <div className="mt-3"><div className="text-sm font-medium mb-1">预览：</div>
            <div className="overflow-x-auto"><table className="table table-xs"><thead><tr><th>类型</th><th>目标类型</th><th>目标ID</th><th>原因</th></tr></thead><tbody>{c.preview.map((p, i) => <tr key={i}><td>{p.type}</td><td>{p.targetType}</td><td>{p.targetId}</td><td>{p.reason}</td></tr>)}</tbody></table></div>
          </div>}
        </div>
      </div>
    </div>
  );
}
