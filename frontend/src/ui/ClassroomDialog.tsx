import type { Classroom } from "../hooks/useClassrooms";

interface ClassroomDialogProps {
  form: Classroom;
  onChange: (form: Classroom) => void;
  saving: boolean;
  onSave: () => void;
  onClose: () => void;
}

export default function ClassroomDialog({
  form,
  onChange,
  saving,
  onSave,
  onClose,
}: ClassroomDialogProps) {
  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-md">
        <h3 className="font-bold text-lg mb-4">
          {form.id ? "编辑教室" : "新增教室"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="label pb-1">
              <span className="label-text">教室名称</span>
            </label>
            <input
              className="input input-bordered w-full"
              value={form.name}
              onChange={(e) => onChange({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label pb-1">
              <span className="label-text">教学楼</span>
            </label>
            <input
              className="input input-bordered w-full"
              value={form.building}
              onChange={(e) => onChange({ ...form, building: e.target.value })}
            />
          </div>
          <div>
            <label className="label pb-1">
              <span className="label-text">容量</span>
            </label>
            <input
              type="number"
              className="input input-bordered w-full"
              value={form.capacity}
              min={1}
              max={300}
              onChange={(e) =>
                onChange({ ...form, capacity: Number(e.target.value) })
              }
            />
          </div>
          <div>
            <label className="label pb-1">
              <span className="label-text">类型</span>
            </label>
            <input
              className="input input-bordered w-full"
              value={form.classroomType}
              onChange={(e) =>
                onChange({ ...form, classroomType: e.target.value })
              }
            />
          </div>
          <div>
            <label className="label pb-1">
              <span className="label-text">状态</span>
            </label>
            <select
              className="select select-bordered w-full"
              value={form.status}
              onChange={(e) => onChange({ ...form, status: e.target.value })}
            >
              <option value="ACTIVE">启用</option>
              <option value="INACTIVE">停用</option>
            </select>
          </div>
        </div>
        <div className="modal-action">
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            取消
          </button>
          <button
            className="btn btn-primary btn-sm"
            disabled={saving}
            onClick={onSave}
          >
            {saving ? (
              <span className="loading loading-spinner loading-xs" />
            ) : (
              "保存"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
