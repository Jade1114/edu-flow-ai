import { useState, useEffect, useMemo } from "react";
import request from "../api/request";
import { useBatchSelection } from "./useBatchSelection";

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
  const [statusFilter, setStatusFilter] = useState("");
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
      const data = await request.get<Classroom[] | { content?: Classroom[] }>("/api/classrooms");
      setClassrooms(Array.isArray(data) ? data : (data as any)?.content ?? []);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    let list = classrooms;
    if (statusFilter) list = list.filter(c => c.status === statusFilter);
    if (!search.trim()) return list;
    const kw = search.toLowerCase();
    return list.filter(
      (c) =>
        c.name.toLowerCase().includes(kw) ||
        c.building.toLowerCase().includes(kw) ||
        c.classroomType.toLowerCase().includes(kw)
    );
  }, [classrooms, search, statusFilter]);

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
    if (!confirm("确认永久删除该教室？如果已被课表或排课结果引用，将无法删除。")) return;
    setDeleting(id);
    try {
      await request.post("/api/management/classrooms/batch-delete", { ids: [id] });
      await loadClassrooms();
    } finally {
      setDeleting(null);
    }
  }

  const batch = useBatchSelection({
    entity: "classrooms",
    label: "教室",
    items: classrooms,
    filtered,
    paged,
    reload: loadClassrooms,
  });

  return {
    paged,
    filtered,
    loading,
    search,
    setSearch: (v: string) => { setSearch(v); setPage(1); batch.clearSelection(); },
    statusFilter,
    setStatusFilter: (v: string) => { setStatusFilter(v); setPage(1); batch.clearSelection(); },
    page,
    setPage,
    pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); batch.clearSelection(); },
    dialogOpen,
    form,
    setForm,
    saving,
    deleting,
    openDialog,
    closeDialog,
    save,
    remove,
    batch,
  };
}
