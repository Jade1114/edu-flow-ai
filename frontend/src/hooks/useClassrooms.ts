import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

export interface Classroom {
  id: number | null;
  name: string;
  building: string;
  capacity: number;
  classroomType: string;
  status: string;
}

const emptyForm: Classroom = {
  id: null,
  name: "",
  building: "",
  capacity: 60,
  classroomType: "普通教室",
  status: "ACTIVE",
};

export function useClassrooms() {
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<Classroom>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => {
    loadClassrooms();
  }, []);

  async function loadClassrooms() {
    setLoading(true);
    try {
      const data = await request.get<Classroom[]>("/api/classrooms");
      setClassrooms(data);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return classrooms;
    const kw = search.toLowerCase();
    return classrooms.filter(
      (c) =>
        c.name.toLowerCase().includes(kw) ||
        c.building.toLowerCase().includes(kw) ||
        c.classroomType.toLowerCase().includes(kw)
    );
  }, [classrooms, search]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  function openDialog(row?: Classroom) {
    setForm(row ? { ...row } : { ...emptyForm });
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
  }

  async function save() {
    setSaving(true);
    try {
      if (form.id) {
        await request.put(`/api/classrooms/${form.id}`, form);
      } else {
        await request.post("/api/classrooms", form);
      }
      setDialogOpen(false);
      await loadClassrooms();
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("确认删除该教室？")) return;
    setDeleting(id);
    try {
      await request.delete(`/api/classrooms/${id}`);
      await loadClassrooms();
    } finally {
      setDeleting(null);
    }
  }

  return {
    paged,
    filtered,
    loading,
    search,
    setSearch: (v: string) => { setSearch(v); setPage(1); },
    page,
    setPage,
    pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); },
    dialogOpen,
    form,
    setForm,
    saving,
    deleting,
    openDialog,
    closeDialog,
    save,
    remove,
  };
}
