import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

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
      const data = await request.get<Teacher[]>("/api/teachers");
      setTeachers(data);
    } finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return teachers;
    const kw = search.toLowerCase();
    return teachers.filter(t =>
      t.employeeNo.toLowerCase().includes(kw) ||
      t.name.toLowerCase().includes(kw) ||
      (t.department?.toLowerCase().includes(kw) ?? false)
    );
  }, [teachers, search]);

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
    if (!confirm("确认删除该教师？")) return;
    setDeleting(id);
    try { await request.delete(`/api/teachers/${id}`); await loadTeachers(); }
    finally { setDeleting(null); }
  }

  return {
    paged, filtered, loading, search,
    setSearch: (v: string) => { setSearch(v); setPage(1); },
    page, setPage, pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); },
    dialogOpen, form, setForm, saving, deleting,
    openDialog, closeDialog, save, remove,
  };
}
