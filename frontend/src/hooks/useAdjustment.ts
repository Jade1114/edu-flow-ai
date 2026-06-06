import { useState, useEffect } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface Req { id: number; reason: string; preferredTimeText: string; status: string; assignmentId: number; createdAt: string; }
interface Assignment { id: number; timeSlotId: number; courseName: string; classroomName: string; teacherName: string; classGroupName: string; weekNumber: number; dayOfWeek: number; periodIndex: number; classroomId: number; }

const DAYS = ["周一","周二","周三","周四","周五","周六","周日"];

export function useAdjustment() {
  const [requests, setRequests] = useState<Req[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [timetableVisible, setTimetableVisible] = useState(false);
  const [currentReq, setCurrentReq] = useState<Req | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [timeSlotMap, setTimeSlotMap] = useState<Record<string, number>>({});
  const [currentWeek, setCurrentWeek] = useState(1);
  const [pendingMove, setPendingMove] = useState<any>(null);
  const [savingMove, setSavingMove] = useState(false);

  useEffect(() => { loadRequests(); }, []);

  async function loadRequests() {
    setLoading(true);
    try {
      const params = statusFilter ? `?status=${statusFilter}` : "";
      setRequests(await request.get(`/api/adjustment-requests${params}`));
    } finally { setLoading(false); }
  }

  async function openTimetable(row: Req) {
    setCurrentReq(await request.get(`/api/adjustment-requests/${row.id}`));
    const [items, slots] = await Promise.all([request.get("/api/course-assignments"), request.get("/api/time-slots")]);
    setAssignments(items);
    const map: Record<string, number> = {};
    (slots as any[]).forEach(s => { map[`${s.weekNumber}-${s.dayOfWeek}-${s.periodIndex}`] = s.id; });
    setTimeSlotMap(map);
    if (items.length > 0) { const minW = Math.min(...items.map((a: Assignment) => a.weekNumber)); if (minW > 0) setCurrentWeek(minW); }
    setTimetableVisible(true);
  }

  async function confirmRequest(row: Req) {
    try {
      await request.post(`/api/adjustment-requests/${row.id}/confirm`, { reviewNote: "确认通过" });
      toast.success("调课已确认");
      loadRequests();
      if (timetableVisible && currentReq?.id === row.id) setTimetableVisible(false);
    } catch { toast.error("操作失败"); }
  }

  async function rejectRequest(row: Req) {
    if (!confirm("确认拒绝该调课申请？")) return;
    try {
      await request.post(`/api/adjustment-requests/${row.id}/reject`, { reviewNote: "教务拒绝" });
      toast.success("已拒绝");
      loadRequests();
      if (timetableVisible && currentReq?.id === row.id) setTimetableVisible(false);
    } catch { toast.error("操作失败"); }
  }

  const weekItems = assignments.filter(a => a.weekNumber === currentWeek);
  const allWeeks = [...new Set(assignments.map(a => a.weekNumber))].sort((a,b)=>a-b);

  function itemsAtSlot(day: number, period: number): Assignment[] {
    const base = weekItems.filter(a => a.dayOfWeek === day && a.periodIndex === period);
    if (!pendingMove) return base;
    return base
      .filter(a => a.id !== pendingMove.itemId)
      .concat(pendingMove.dayOfWeek === day && pendingMove.periodIndex === period && pendingMove.weekNumber === currentWeek
        ? [weekItems.find(a => a.id === pendingMove.itemId)].filter(Boolean).map(a => ({...a!, dayOfWeek: day, periodIndex: period, timeSlotId: pendingMove.targetTimeSlotId}))
        : []);
  }

  function isAdjustTarget(item: Assignment) { return currentReq && item.id === currentReq.assignmentId; }

  function onSlotClick(item: Assignment) {
    if (!isAdjustTarget(item)) { toast.warning("只能移动标黄的调课片段"); return; }
    if (!pendingMove) { setPendingMove({ itemId: item.id, dayOfWeek: item.dayOfWeek, periodIndex: item.periodIndex, weekNumber: currentWeek }); return; }
    const key = `${currentWeek}-${item.dayOfWeek}-${item.periodIndex}`; const tsId = timeSlotMap[key];
    if (!tsId) { toast.warning("时间段不存在"); return; }
    setPendingMove({...pendingMove, targetTimeSlotId: tsId, dayOfWeek: item.dayOfWeek, periodIndex: item.periodIndex, weekNumber: currentWeek });
  }

  async function saveMove() {
    if (!pendingMove?.targetTimeSlotId) return;
    setSavingMove(true);
    try {
      const orig = assignments.find(a => a.id === pendingMove.itemId);
      await request.put(`/api/course-assignments/${pendingMove.itemId}/move`, null, { params: { timeSlotId: pendingMove.targetTimeSlotId, classroomId: orig?.classroomId } });
      await request.post(`/api/adjustment-requests/${currentReq!.id}/confirm`, { reviewNote: "已通过拖拽调整" });
      toast.success("调课成功");
      setPendingMove(null);
      const [items] = await Promise.all([request.get("/api/course-assignments"), loadRequests()]);
      setAssignments(items);
    } catch {} finally { setSavingMove(false); }
  }

  return { requests, loading, statusFilter, setStatusFilter: (v: string) => { setStatusFilter(v); loadRequests(); }, timetableVisible, setTimetableVisible, currentReq, currentWeek, setCurrentWeek, pendingMove, setPendingMove, savingMove, weekItems, allWeeks, DAYS, itemsAtSlot, isAdjustTarget, loadRequests, openTimetable, confirmRequest, rejectRequest, onSlotClick, saveMove };
}
