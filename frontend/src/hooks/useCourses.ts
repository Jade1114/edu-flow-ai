import { useState, useEffect, useMemo } from "react";
import request from "../api/request";
import { useBatchSelection } from "./useBatchSelection";

export interface Course {
  id: number | null;
  name: string;
  code: string;
  credits: number;
  courseType: string;
  requiredRoomType: string;
  requiredHours: number;
  description?: string;
  status: string;
}

const emptyForm: Course = {
  id: null,
  name: "",
  code: "",
  credits: 0,
  courseType: "",
  requiredRoomType: "",
  requiredHours: 32,
  description: "",
  status: "ACTIVE",
};

export function useCourses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<Course>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => {
    loadCourses();
  }, []);

  async function loadCourses() {
    setLoading(true);
    try {
      const data = await request.get<Course[] | { content?: Course[] }>("/api/courses");
      setCourses(Array.isArray(data) ? data : data?.content ?? []);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    let list = courses;
    if (statusFilter) list = list.filter(c => c.status === statusFilter);
    if (!search.trim()) return list;
    const kw = search.toLowerCase();
    return list.filter(
      (c) =>
        c.name.toLowerCase().includes(kw) ||
        c.code.toLowerCase().includes(kw) ||
        c.courseType.toLowerCase().includes(kw)
    );
  }, [courses, search, statusFilter]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  function openDialog(row?: Course) {
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
        await request.put(`/api/courses/${form.id}`, form);
      } else {
        await request.post("/api/courses", form);
      }
      setDialogOpen(false);
      await loadCourses();
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("确认永久删除该课程？如果已被教学任务引用，将无法删除。")) return;
    setDeleting(id);
    try {
      await request.post("/api/management/courses/batch-delete", { ids: [id] });
      await loadCourses();
    } finally {
      setDeleting(null);
    }
  }

  const batch = useBatchSelection({
    entity: "courses",
    label: "课程",
    items: courses,
    filtered,
    paged,
    reload: loadCourses,
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
