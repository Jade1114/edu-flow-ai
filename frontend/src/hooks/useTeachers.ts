import { useState, useEffect, useMemo } from "react";
import request from "../api/request";
import { useBatchSelection } from "./useBatchSelection";

export interface Teacher {
  id: number | null;
  employeeNo: string;
  name: string;
  department: string;
  title: string;
  maxWeeklyHours: number;
  status: string;
  role: string;
  password: string;
}

const emptyForm: Teacher = {
  id: null,
  employeeNo: "",
  name: "",
  department: "",
  title: "",
  maxWeeklyHours: 8,
  status: "ACTIVE",
  role: "TEACHER",
  password: "123456",
};

export function useTeachers() {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<Teacher>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => { loadTeachers(); }, []);

  async function loadTeachers() {
    setLoading(true);
    try {
      const data = await request.get<Teacher[] | { content?: Teacher[] }>("/api/teachers");
      setTeachers(Array.isArray(data) ? data : data?.content ?? []);
    } finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    let list = teachers;
    if (statusFilter) list = list.filter(t => t.status === statusFilter);
    if (!search.trim()) return list;
    const kw = search.toLowerCase();
    return list.filter(t =>
      t.employeeNo.toLowerCase().includes(kw) ||
      t.name.toLowerCase().includes(kw) ||
      (t.department?.toLowerCase().includes(kw) ?? false)
    );
  }, [teachers, search, statusFilter]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  function openDialog(row?: Teacher) {
    setForm(row ? { ...row, password: "" } : { ...emptyForm });
    setDialogOpen(true);
  }
  function closeDialog() { setDialogOpen(false); }

  async function save() {
    setSaving(true);
    try {
      if (form.id) await request.put(`/api/teachers/${form.id}`, form);
      else await request.post("/api/teachers", form);
      setDialogOpen(false);
      await loadTeachers();
    } finally { setSaving(false); }
  }

  async function remove(id: number) {
    if (!confirm("确认永久删除该教师？如果已被教学任务引用，将无法删除。")) return;
    setDeleting(id);
    try {
      await request.post("/api/management/teachers/batch-delete", { ids: [id] });
      await loadTeachers();
    }
    finally { setDeleting(null); }
  }

  const batch = useBatchSelection({
    entity: "teachers",
    label: "教师",
    items: teachers,
    filtered,
    paged,
    reload: loadTeachers,
  });

  return {
    paged, filtered, loading, search,
    setSearch: (v: string) => { setSearch(v); setPage(1); batch.clearSelection(); },
    statusFilter, setStatusFilter: (v: string) => { setStatusFilter(v); setPage(1); batch.clearSelection(); },
    page, setPage, pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); batch.clearSelection(); },
    dialogOpen, form, setForm, saving, deleting,
    openDialog, closeDialog, save, remove,
    batch,
  };
}
