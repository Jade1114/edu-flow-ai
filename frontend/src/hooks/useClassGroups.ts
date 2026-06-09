import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import request from "../api/request";

export interface ClassGroup {
  id: number | null;
  name: string;
  major: string;
  department: string;
  grade: string;
  studentCount: number;
}

const emptyForm: ClassGroup = {
  id: null,
  name: "",
  major: "",
  department: "",
  grade: "",
  studentCount: 30,
};

export function useClassGroups() {
  const [groups, setGroups] = useState<ClassGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [gradeFilter, setGradeFilter] = useState("");
  const [majorFilter, setMajorFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<ClassGroup>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => { loadGroups(); }, []);

  async function loadGroups() {
    setLoading(true);
    try {
      const data = await request.get<ClassGroup[] | { content?: ClassGroup[] }>("/api/class-groups");
      setGroups(Array.isArray(data) ? data : data?.content ?? []);
    } catch (error) {
      toast.error("班级数据加载失败");
      throw error;
    } finally { setLoading(false); }
  }

  const gradeOptions = useMemo(() => unique(groups.map(g => g.grade)), [groups]);
  const majorOptions = useMemo(() => unique(groups.map(g => g.major)), [groups]);
  const departmentOptions = useMemo(() => unique(groups.map(g => g.department)), [groups]);

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return groups.filter(g => {
      const matchedKeyword = !kw || [g.name, g.major, g.department, g.grade].some(value => (value || "").toLowerCase().includes(kw));
      const matchedGrade = !gradeFilter || g.grade === gradeFilter;
      const matchedMajor = !majorFilter || g.major === majorFilter;
      const matchedDepartment = !departmentFilter || g.department === departmentFilter;
      return matchedKeyword && matchedGrade && matchedMajor && matchedDepartment;
    });
  }, [groups, search, gradeFilter, majorFilter, departmentFilter]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  const totalStudents = useMemo(() => filtered.reduce((sum, group) => sum + Number(group.studentCount || 0), 0), [filtered]);
  const hasFilter = Boolean(search || gradeFilter || majorFilter || departmentFilter);

  function openDialog(row?: ClassGroup) {
    setForm(row ? { ...row } : { ...emptyForm });
    setDialogOpen(true);
  }

  function closeDialog() { setDialogOpen(false); }

  function resetFilters() {
    setSearch("");
    setGradeFilter("");
    setMajorFilter("");
    setDepartmentFilter("");
    setPage(1);
  }

  function validateForm() {
    if (!form.name.trim()) return "班级名称不能为空";
    if (!form.major.trim()) return "专业不能为空";
    if (!form.department.trim()) return "院系不能为空";
    if (!form.grade.trim()) return "年级不能为空";
    if (!Number.isFinite(Number(form.studentCount)) || Number(form.studentCount) <= 0) return "班级人数必须大于0";
    return null;
  }

  async function save() {
    const error = validateForm();
    if (error) {
      toast.error(error);
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, name: form.name.trim(), major: form.major.trim(), department: form.department.trim(), grade: form.grade.trim(), studentCount: Number(form.studentCount) };
      if (form.id) await request.put(`/api/class-groups/${form.id}`, payload);
      else await request.post("/api/class-groups", payload);
      toast.success(form.id ? "班级已更新" : "班级已新增");
      setDialogOpen(false);
      await loadGroups();
    } catch (error) {
      toast.error("保存班级失败");
      throw error;
    } finally { setSaving(false); }
  }

  async function remove(id: number) {
    if (!confirm("确认删除该班级？如果已被教学任务引用，将无法删除。")) return;
    setDeleting(id);
    try {
      await request.delete(`/api/class-groups/${id}`);
      toast.success("班级已删除");
      await loadGroups();
    } catch (error) {
      toast.error("删除班级失败，可能已被教学任务引用");
      throw error;
    } finally { setDeleting(null); }
  }

  return {
    groups, paged, filtered, loading, search,
    setSearch: (v: string) => { setSearch(v); setPage(1); },
    gradeFilter, setGradeFilter: (v: string) => { setGradeFilter(v); setPage(1); },
    majorFilter, setMajorFilter: (v: string) => { setMajorFilter(v); setPage(1); },
    departmentFilter, setDepartmentFilter: (v: string) => { setDepartmentFilter(v); setPage(1); },
    gradeOptions, majorOptions, departmentOptions,
    page, setPage, pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); },
    dialogOpen, form, setForm, saving, deleting,
    totalStudents, hasFilter, resetFilters,
    openDialog, closeDialog, save, remove, reload: loadGroups,
  };
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b, "zh-CN"));
}
