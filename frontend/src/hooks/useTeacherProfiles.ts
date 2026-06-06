import { useState, useEffect, useMemo } from "react";
import request from "../api/request";

interface TeacherProfile {
  teacher_id: number | null; teacher_name: string; observation_count: number;
  declared_profile?: any; feedback_profile?: any; feedback_confidence?: number;
  derived_from_data: any; final_profile: any;
}

interface TeacherProfileDoc { profile_version: string; generated_at: string; teacher_count: number; profiles: TeacherProfile[]; }
interface SatisfactionReport { report_version: string; generated_at: string; scheme_count: number; schemes: any[]; }

export function useTeacherProfiles() {
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [profileDoc, setProfileDoc] = useState<TeacherProfileDoc | null>(null);
  const [satisfactionReport, setSatisfactionReport] = useState<SatisfactionReport | null>(null);
  const [keyword, setKeyword] = useState("");
  const [declaredFilter, setDeclaredFilter] = useState("all");
  const [feedbackFilter, setFeedbackFilter] = useState("all");
  const [satisfactionFilter, setSatisfactionFilter] = useState("all");
  const [tagFilter, setTagFilter] = useState("all");
  const [selectedProfile, setSelectedProfile] = useState<TeacherProfile | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);

  const profiles = useMemo(() => profileDoc?.profiles || [], [profileDoc]);

  const filtered = useMemo(() => {
    let list = profiles;
    if (keyword.trim()) {
      const kw = keyword.toLowerCase();
      list = list.filter(p => p.teacher_name?.toLowerCase().includes(kw) || String(p.teacher_id).includes(kw));
    }
    if (declaredFilter === "yes") list = list.filter(p => p.declared_profile);
    else if (declaredFilter === "no") list = list.filter(p => !p.declared_profile);
    if (feedbackFilter === "yes") list = list.filter(p => p.feedback_profile);
    else if (feedbackFilter === "no") list = list.filter(p => !p.feedback_profile);
    if (satisfactionFilter === "low") {
      const report = satisfactionReport?.schemes?.[0];
      if (report) {
        const lowIds = new Set((report.low_satisfaction_teachers || []).map((t: any) => t.teacher_id));
        list = list.filter(p => p.teacher_id !== null && lowIds.has(p.teacher_id));
      }
    }
    if (tagFilter === "early") list = list.filter(p => p.final_profile?.avoid_early_period);
    else if (tagFilter === "late") list = list.filter(p => p.final_profile?.avoid_late_period);
    return list;
  }, [profiles, keyword, declaredFilter, feedbackFilter, satisfactionFilter, tagFilter, satisfactionReport]);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true); setReportLoading(true);
    try {
      const [doc, report] = await Promise.all([
        request.get("/api/ml/teacher-profiles/latest"),
        request.get("/api/ml/teacher-profiles/satisfaction/latest"),
      ]);
      setProfileDoc(doc);
      setSatisfactionReport(report);
    } catch { setProfileDoc(null); setSatisfactionReport(null); }
    finally { setLoading(false); setReportLoading(false); }
  }

  function openDetail(profile: TeacherProfile) { setSelectedProfile(profile); setDetailVisible(true); }

  const latestScheme = satisfactionReport?.schemes?.[0];
  const avgSatisfaction = latestScheme?.summary?.avg_satisfaction_score ?? 0;

  return { loading, reportLoading, profileDoc, satisfactionReport, keyword, setKeyword, declaredFilter, setDeclaredFilter, feedbackFilter, setFeedbackFilter, satisfactionFilter, setSatisfactionFilter, tagFilter, setTagFilter, profiles, filtered, selectedProfile, detailVisible, setDetailVisible, openDetail, loadAll, latestScheme, avgSatisfaction };
}
