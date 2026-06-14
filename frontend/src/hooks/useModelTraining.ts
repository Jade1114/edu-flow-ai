import { useState, useEffect, useRef } from "react";
import request from "../api/request";
import { toast } from "sonner";

interface FeedbackStats {
  schemeCount: number; itemCount: number; feedbackCount: number;
  adjustmentCount: number; conflictCount: number; eventCount: number; exportPath: string;
}

interface EventSummary {
  eventCount: number;
  eventTypes: { eventType: string; eventCount: number }[];
  recentEvents: Record<string, unknown>[];
}

interface TrainingLog {
  id: number; modelVersion: string; trainingType: string;
  sampleCount: number; positiveCount: number; negativeCount: number;
  evalAuc?: number; evalAccuracy?: number; metricsJson?: string;
  status: string; message?: string; createdAt: string;
}

const EVENT_LABEL: Record<string, string> = {
  SCHEME_CONFIRMED: "方案确认", ITEM_MOVED: "片段移动",
  ITEM_MARKED_GOOD: "人工标好", ITEM_MARKED_BAD: "人工标差",
};

export function useModelTraining() {
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [eventSummary, setEventSummary] = useState<EventSummary | null>(null);
  const [eventLoading, setEventLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [historyTraining, setHistoryTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<Record<string, unknown> | null>(null);
  const [historyTrainResult, setHistoryTrainResult] = useState<Record<string, unknown> | null>(null);
  const [historyTrainingLogs, setHistoryTrainingLogs] = useState<string[]>([]);
  const historyEventSourceRef = useRef<EventSource | null>(null);
  const [trainingLogs, setTrainingLogs] = useState<TrainingLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  useEffect(() => {
    loadAll();
    return () => historyEventSourceRef.current?.close();
  }, []);

  async function loadAll() {
    await Promise.all([loadLatestFeedback(), loadEventSummary(), loadTrainingLogs()]);
  }

  async function loadLatestFeedback(taskId?: string) {
    setFeedbackLoading(true);
    try {
      const params = taskId ? `?taskId=${taskId}` : "";
      setFeedbackStats(await request.get(`/api/ml/feedback/latest-export${params}`));
    } catch { setFeedbackStats(null); }
    finally { setFeedbackLoading(false); }
  }

  async function loadEventSummary(taskId?: string) {
    setEventLoading(true);
    try {
      const params = taskId ? `?taskId=${taskId}&recentLimit=100` : "?recentLimit=100";
      setEventSummary(await request.get(`/api/ml/feedback/events/summary${params}`));
    } catch { setEventSummary(null); }
    finally { setEventLoading(false); }
  }

  async function generateFeedback(taskId?: string) {
    setFeedbackLoading(true);
    try {
      const params = taskId ? `?taskId=${taskId}` : "";
      setFeedbackStats(await request.get(`/api/ml/feedback/export${params}`));
      loadEventSummary(taskId);
      toast.success("反馈 JSON 已生成");
    } catch { toast.error("生成反馈 JSON 失败"); }
    finally { setFeedbackLoading(false); }
  }

  function trainFromHistory(rawDir?: string) {
    if (!rawDir) { toast.error("请指定历史课表目录路径"); return; }
    historyEventSourceRef.current?.close();
    setHistoryTraining(true);
    setHistoryTrainingLogs([]);
    setHistoryTrainResult({ status: "RUNNING" });

    const source = new EventSource(`/api/ml/feedback/train-from-history/stream?rawDir=${encodeURIComponent(rawDir)}`);
    historyEventSourceRef.current = source;

    source.addEventListener("log", (event) => {
      setHistoryTrainingLogs((logs) => [...logs, event.data]);
    });

    source.addEventListener("done", (event) => {
      try {
        const result = JSON.parse(event.data);
        setHistoryTrainResult(result);
        toast.success("历史数据训练完成！");
        loadTrainingLogs();
      } catch {
        setHistoryTrainResult({ status: "ok", rawOutput: event.data });
      }
      setHistoryTraining(false);
      source.close();
      historyEventSourceRef.current = null;
    });

    source.addEventListener("failed", (event) => {
      let message = event.data || "未知错误";
      try { message = JSON.parse(event.data).message || message; } catch {}
      setHistoryTrainResult({ status: "FAILED", error: message });
      setHistoryTraining(false);
      toast.error(`训练失败: ${message}`);
      source.close();
      historyEventSourceRef.current = null;
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return;
      setHistoryTrainResult({ status: "FAILED", error: "训练日志连接中断" });
      setHistoryTraining(false);
      toast.error("训练日志连接中断");
      source.close();
      historyEventSourceRef.current = null;
    };
  }

  async function triggerRetrain(taskId?: string) {
    setTraining(true);
    setTrainResult({ status: "RUNNING", message: "正在将最新反馈 JSON 转为训练样本..." });
    try {
      const params = taskId ? `?taskId=${taskId}` : "";
      const result = await request.post(`/api/ml/feedback/train${params}`);
      setTrainResult(result);
      if (result.status === "SUCCEEDED") {
        toast.success(`训练完成！${result.sampleCount || 0} 条样本`);
        loadTrainingLogs();
      } else toast.error(`训练失败: ${result.message}`);
    } catch (e: any) {
      setTrainResult({ status: "FAILED", message: e.message || "请求失败" });
      toast.error("重训请求失败");
    } finally { setTraining(false); }
  }

  async function loadTrainingLogs() {
    setLogsLoading(true);
    try { setTrainingLogs(await request.get("/api/ml/feedback/training-logs?limit=20")); }
    catch { setTrainingLogs([]); }
    finally { setLogsLoading(false); }
  }

  const lastLog = trainingLogs[0];
  const positiveRate = lastLog ? Math.round(((lastLog.positiveCount || 0) / (lastLog.sampleCount || 1)) * 100) : 0;

  const eventCards = [
    { label: "事件总数", value: eventSummary?.eventCount || 0 },
    { label: "方案确认", value: eventSummary?.eventTypes?.find(t => t.eventType === "SCHEME_CONFIRMED")?.eventCount || 0 },
    { label: "片段移动", value: eventSummary?.eventTypes?.find(t => t.eventType === "ITEM_MOVED")?.eventCount || 0 },
    { label: "人工标注", value: (eventSummary?.eventTypes?.find(t => t.eventType === "ITEM_MARKED_GOOD")?.eventCount || 0) + (eventSummary?.eventTypes?.find(t => t.eventType === "ITEM_MARKED_BAD")?.eventCount || 0) },
  ];

  function eventLabel(type: string) { return EVENT_LABEL[type] || type || "-"; }
  function typeLabel(type: string) { return ({ INITIAL: "初始训练", FEEDBACK: "反馈重训", FULL: "全量训练", HISTORY: "历史数据训练" } as any)[type] || type || "-"; }
  function fmtTime(t: string) { return t ? t.replace("T", " ").substring(0, 19) : "-"; }

  return { feedbackStats, feedbackLoading, eventSummary, eventLoading, training, historyTraining, trainResult, historyTrainResult, historyTrainingLogs, trainingLogs, logsLoading, lastLog, positiveRate, eventCards, eventLabel, typeLabel, fmtTime, loadAll, loadLatestFeedback, loadEventSummary, generateFeedback, triggerRetrain, trainFromHistory, loadTrainingLogs };
}
