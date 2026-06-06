import type { ClassGroup } from "../hooks/useClassGroups";

interface Props { form: ClassGroup; onChange: (f: ClassGroup) => void; saving: boolean; onSave: () => void; onClose: () => void; }

export default function ClassGroupDialog({ form, onChange, saving, onSave, onClose }: Props) {
  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-md">
        <h3 className="font-bold text-lg mb-4">{form.id ? "编辑班级" : "新增班级"}</h3>
        <div className="space-y-3">
          <div><label className="label pb-1"><span className="label-text">班级名称</span></label><input className="input input-bordered w-full" value={form.name} onChange={e => onChange({...form, name: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">专业</span></label><input className="input input-bordered w-full" value={form.major} onChange={e => onChange({...form, major: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">院系</span></label><input className="input input-bordered w-full" value={form.department} onChange={e => onChange({...form, department: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">年级</span></label><input className="input input-bordered w-full" value={form.grade} onChange={e => onChange({...form, grade: e.target.value})} /></div>
          <div><label className="label pb-1"><span className="label-text">人数</span></label><input type="number" className="input input-bordered w-full" value={form.studentCount} min={0} onChange={e => onChange({...form, studentCount: Number(e.target.value)})} /></div>
        </div>
        <div className="modal-action">
          <button className="btn btn-ghost btn-sm" onClick={onClose}>取消</button>
          <button className="btn btn-primary btn-sm" disabled={saving} onClick={onSave}>{saving ? <span className="loading loading-spinner loading-xs" /> : "保存"}</button>
        </div>
      </div>
    </div>
  );
}
