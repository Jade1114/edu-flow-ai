import type { ClassGroup } from "../hooks/useClassGroups";

interface Props {
  form: ClassGroup;
  onChange: (f: ClassGroup) => void;
  saving: boolean;
  onSave: () => void;
  onClose: () => void;
}

export default function ClassGroupDialog({ form, onChange, saving, onSave, onClose }: Props) {
  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-lg">
        <h3 className="font-bold text-lg mb-1">{form.id ? "编辑班级" : "新增班级"}</h3>
        <p className="text-xs text-base-content/50 mb-4">班级数据会作为教学任务生成的基础主数据，建议信息填完整。</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="form-control md:col-span-2">
            <div className="label py-1"><span className="label-text">班级名称 <span className="text-error">*</span></span></div>
            <input className="input input-bordered w-full" placeholder="如 2025级计算机科学与技术1班" value={form.name} onChange={e => onChange({ ...form, name: e.target.value })} />
          </label>
          <label className="form-control">
            <div className="label py-1"><span className="label-text">专业 <span className="text-error">*</span></span></div>
            <input className="input input-bordered w-full" placeholder="如 计算机科学与技术" value={form.major} onChange={e => onChange({ ...form, major: e.target.value })} />
          </label>
          <label className="form-control">
            <div className="label py-1"><span className="label-text">院系 <span className="text-error">*</span></span></div>
            <input className="input input-bordered w-full" placeholder="如 电子信息与计算机工程系" value={form.department} onChange={e => onChange({ ...form, department: e.target.value })} />
          </label>
          <label className="form-control">
            <div className="label py-1"><span className="label-text">年级 <span className="text-error">*</span></span></div>
            <input className="input input-bordered w-full" placeholder="如 2025" value={form.grade} onChange={e => onChange({ ...form, grade: e.target.value })} />
          </label>
          <label className="form-control">
            <div className="label py-1"><span className="label-text">人数 <span className="text-error">*</span></span></div>
            <input type="number" className="input input-bordered w-full" value={form.studentCount} min={1} onChange={e => onChange({ ...form, studentCount: Number(e.target.value) })} />
          </label>
        </div>
        <div className="modal-action">
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={saving}>取消</button>
          <button className="btn btn-primary btn-sm" disabled={saving} onClick={onSave}>{saving ? <span className="loading loading-spinner loading-xs" /> : "保存"}</button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={saving ? undefined : onClose} />
    </div>
  );
}
