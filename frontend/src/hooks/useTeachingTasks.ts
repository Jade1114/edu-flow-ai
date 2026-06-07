import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

interface Course { id: number; name: string; code: string; courseType: string; requiredHours: number; }
interface Teacher { id: number; name: string; }
interface ClassGroup { id: number; name: string; }
interface Classroom { id: number; name: string; building: string; capacity: number; }

export interface TeachingTask {
  id: number | null;
  courseId: number | "";
  courseType: string;
  requiredRoomType: string;
  primaryTeacherId: number | "";
  assistantTeacherId?: number | "";
  classroomId?: number | "";
  classGroupIds: number[];
  totalHours: number;
  notes?: string;
  status: string;
  course?: Course;
  primaryTeacher?: Teacher;
  assistantTeacher?: Teacher;
  classroom?: Classroom;
  classGroups?: ClassGroup[];
}

const courseTypeOptions = [
  { value: "理论课", room: "普通教室" },
  { value: "上机课", room: "机房" },
  { value: "实践课", room: "" },
];

const emptyForm: TeachingTask = {
  id: null, courseId: "", courseType: "理论课", requiredRoomType: "普通教室",
  primaryTeacherId: "", assistantTeacherId: "", classroomId: "",
  classGroupIds: [], totalHours: 32, notes: "", status: "ACTIVE",
};

export function useTeachingTasks() {
  const [tasks, setTasks] = useState<TeachingTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [courseTypeFilter, setCourseTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<TeachingTask>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [classGroups, setClassGroups] = useState<ClassGroup[]>([]);
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const unwrap = (d: any) => Array.isArray(d) ? d : d?.content ?? [];
      const [t, c, te, cg, cr] = await Promise.all([
        request.get<TeachingTask[]>("/api/teaching-tasks"),
        request.get<Course[]>("/api/courses"),
        request.get<Teacher[]>("/api/teachers"),
        request.get<ClassGroup[]>("/api/class-groups"),
        request.get<Classroom[]>("/api/classrooms"),
      ]);
      setTasks(unwrap(t)); setCourses(unwrap(c)); setTeachers(unwrap(te)); setClassGroups(unwrap(cg)); setClassrooms(cr);
    } finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    let list = tasks;
    if (search.trim()) {
      const kw = search.toLowerCase();
      list = list.filter(t =>
        t.course?.name?.toLowerCase().includes(kw) ||
        t.primaryTeacher?.name?.toLowerCase().includes(kw) ||
        t.assistantTeacher?.name?.toLowerCase().includes(kw) ||
        t.classGroups?.some(cg => cg.name.toLowerCase().includes(kw))
      );
    }
    if (courseTypeFilter) list = list.filter(t => t.course?.courseType === courseTypeFilter);
    return list;
  }, [tasks, search, courseTypeFilter]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  function onCourseChanged(courseId: number) {
    const course = courses.find(c => c.id === courseId);
    if (course) {
      const opt = courseTypeOptions.find(o => o.value === course.courseType);
      setForm(f => ({
        ...f, courseId,
        courseType: course.courseType || f.courseType,
        requiredRoomType: opt?.room || "",
        totalHours: course.requiredHours || 32,
      }));
    }
  }

  function onCourseTypeChanged(type: string) {
    const opt = courseTypeOptions.find(o => o.value === type);
    setForm(f => ({
      ...f, courseType: type,
      requiredRoomType: opt?.room || "",
    }));
  }

  function openDialog(row?: TeachingTask) {
    if (row) {
      setForm({
        id: row.id,
        courseId: row.courseId ?? "",
        courseType: row.course?.courseType || row.courseType || "理论课",
        requiredRoomType: row.requiredRoomType || "",
        primaryTeacherId: row.primaryTeacherId ?? "",
        assistantTeacherId: row.assistantTeacherId ?? "",
        classroomId: row.classroomId ?? "",
        classGroupIds: row.classGroups?.map(cg => cg.id) ?? row.classGroupIds ?? [],
        totalHours: row.totalHours || 32,
        notes: row.notes || "",
        status: row.status || "ACTIVE",
      });
    } else {
      setForm({ ...emptyForm });
    }
    setDialogOpen(true);
  }

  function closeDialog() { setDialogOpen(false); }

  async function save() {
    setSaving(true);
    try {
      const roomMap: Record<string, string> = { "理论课": "普通教室", "上机课": "机房", "实践课": "" };
      if (form.id) {
        await request.put(`/api/teaching-tasks/${form.id}`, form);
      } else {
        await request.post("/api/teaching-tasks", {
          ...form,
          requiredRoomType: roomMap[form.courseType] || "",
        });
      }
      setDialogOpen(false);
      await loadAll();
    } finally { setSaving(false); }
  }

  async function remove(id: number) {
    if (!confirm("确认删除该教学任务？")) return;
    setDeleting(id);
    try { await request.delete(`/api/teaching-tasks/${id}`); await loadAll(); }
    finally { setDeleting(null); }
  }

  return {
    paged, filtered, loading, search,
    setSearch: (v: string) => { setSearch(v); setPage(1); },
    courseTypeFilter, setCourseTypeFilter: (v: string) => { setCourseTypeFilter(v); setPage(1); },
    page, setPage, pageSize,
    setPageSize: (v: number) => { setPageSize(v); setPage(1); },
    dialogOpen, form, setForm, saving, deleting,
    courses, teachers, classGroups, classrooms,
    openDialog, closeDialog, save, remove,
    onCourseChanged, onCourseTypeChanged,
  };
}
