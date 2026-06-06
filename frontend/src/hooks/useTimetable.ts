import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

interface Assignment {
  id: number;
  courseName: string;
  classGroupName: string;
  teacherName: string;
  classroomName: string;
  timeSlotLabel: string;
  weekNumber: number;
  dayOfWeek: number;
  periodIndex: number;
  status: string;
}

const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export function useTimetable() {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const [currentWeek, setCurrentWeek] = useState(1);
  const [filters, setFilters] = useState({
    teacherId: "", classGroupId: "", courseId: "", weekNumber: "", dayOfWeek: "",
  });

  useEffect(() => { loadAssignments(); }, []);

  async function loadAssignments() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
      const qs = params.toString();
      const data = await request.get<Assignment[]>(`/api/course-assignments${qs ? "?" + qs : ""}`);
      setAssignments(data);
      if (data.length > 0) {
        const minWeek = Math.min(...data.map(a => a.weekNumber));
        if (minWeek > 0) setCurrentWeek(minWeek);
      }
    } finally { setLoading(false); }
  }

  const weekItems = useMemo(() =>
    assignments.filter(a => a.weekNumber === currentWeek),
    [assignments, currentWeek]
  );

  const allWeeks = useMemo(() =>
    [...new Set(assignments.map(a => a.weekNumber))].sort((a, b) => a - b),
    [assignments]
  );

  function itemsAtSlot(dayOfWeek: number, periodIndex: number) {
    return weekItems.filter(a => a.dayOfWeek === dayOfWeek && a.periodIndex === periodIndex);
  }

  return {
    assignments, loading, viewMode, setViewMode,
    currentWeek, setCurrentWeek,
    filters, setFilters,
    weekItems, allWeeks, dayNames,
    itemsAtSlot,
    loadAssignments,
  };
}
