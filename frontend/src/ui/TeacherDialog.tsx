import type { Teacher } from "../hooks/useTeachers";

interface Props { form: Teacher; onChange: (f: Teacher) => void; saving: boolean; onSave: () => void; onClose: () => void; }

export default function TeacherDialog({ form, onChange, saving, onSave, onClose }: Props) {
  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-md">
        <h3 className="font-bold text-lg mb-4">{form.id ? "编辑教师" : "新增教师"}</h3>
        <div className="space-y-3">
          <div><label className="label pb-1"><span className="label-text">工号</span></label><input className="input input-bordered w-full" value={form.employeeNo} disabled={!!form.id} onChange={e => onChange({...form, employeeNo: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">姓名</span></label><input className="input input-bordered w-full" value={form.name} onChange={e => onChange({...form, name: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">部门</span></label><input className="input input-bordered w-full" value={form.department} onChange={e => onChange({...form, department: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">职称</span></label><input className="input input-bordered w-full" value={form.title} onChange={e => onChange({...form, title: e.target.value})} /></div>
          <div>
            <label className="label pb-1"><span className="label-text">角色</span></label>
            <select className="select select-bordered w-full" value={form.role} onChange={e => onChange({...form, role: e.target.value})}>
              <option value="TEACHER">教师</option><option value="ADMIN">管理员</option>
            </select>
          </div>
          {!form.id && <div><label className="label pb-1"><span className="label-text">密码</span></label><input className="input input-bordered w-full" value={form.password} onChange={e => onChange({...form, password: e.target.value})} /></div>}
          <div>
            <label className="label pb-1"><span className="label-text">状态</span></label>
            <select className="select select-bordered w-full" value={form.status} onChange={e => onChange({...form, status: e.target.value})}>
              <option value="ACTIVE">启用</option><option value="INACTIVE">停用</option>
            </select>
          </div>
        </div>
        <div className="modal-action">
          <button className="btn btn-ghost btn-sm" onClick={onClose}>取消</button>
          <button className="btn btn-primary btn-sm" disabled={saving} onClick={onSave}>{saving ? <span className="loading loading-spinner loading-xs" /> : "保存"}</button>
        </div>
      </div>
    </div>
  );
}
