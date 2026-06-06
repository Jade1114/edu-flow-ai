import { useState, useEffect, useMemo } from "react";
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
  studentCount: 0,
};

export function useClassGroups() {
  const [groups, setGroups] = useState<ClassGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
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
      const data = await request.get<ClassGroup[]>("/api/class-groups");
      setGroups(data);
    } finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return groups;
    const kw = search.toLowerCase();
    return groups.filter(g => g.name.toLowerCase().includes(kw) || g.major.toLowerCase().includes(kw));
  }, [groups, search]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  function openDialog(row?: ClassGroup) {
    setForm(row ? { ...row } : { ...emptyForm });
    setDialogOpen(true);
  }
  function closeDialog() { setDialogOpen(false); }

  async function save() {
    setSaving(true);
    try {
      if (form.id) await request.put(`/api/class-groups/${form.id}`, form);
      else await request.post("/api/class-groups", form);
      setDialogOpen(false);
      await loadGroups();
    } finally { setSaving(false); }
  }

  async function remove(id: number) {
    if (!confirm("确认删除该班级？")) return;
    setDeleting(id);
    try { await request.delete(`/api/class-groups/${id}`); await loadGroups(); }
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
