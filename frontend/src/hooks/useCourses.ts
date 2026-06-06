import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

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
      const data = await request.get<Course[]>("/api/courses");
      setCourses(data);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return courses;
    const kw = search.toLowerCase();
    return courses.filter(
      (c) =>
        c.name.toLowerCase().includes(kw) ||
        c.code.toLowerCase().includes(kw) ||
        c.courseType.toLowerCase().includes(kw)
    );
  }, [courses, search]);

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
    if (!confirm("确认删除该课程？")) return;
    setDeleting(id);
    try {
      await request.delete(`/api/courses/${id}`);
      await loadCourses();
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
