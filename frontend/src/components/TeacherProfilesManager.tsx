import { useTeacherProfiles } from "../hooks/useTeacherProfiles";

function RateBar({ rate, label }: { rate: number; label: string }) {
  return <div className="flex items-center gap-2"><span className="text-xs w-12 text-right">{label}</span><div className="flex-1 h-2 rounded bg-base-200"><div className="h-full rounded bg-primary transition-all" style={{ width: `${Math.round(rate * 100)}%` }} /></div><span className="text-xs w-10">{Math.round(rate * 100)}%</span></div>;
}

export default function TeacherProfilesManager() {
  const p = useTeacherProfiles();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div><h2>教师画像分析</h2>{p.profileDoc && <p className="text-sm text-base-content/50 mt-1">版本 {p.profileDoc.profile_version} · {p.profileDoc.teacher_count} 位教师 · {p.profileDoc.generated_at?.replace("T"," ").substring(0,19)}</p>}</div>
        <button className="btn btn-ghost btn-sm" disabled={p.loading} onClick={p.loadAll}>刷新</button>
      </div>

      {/* Satisfaction summary */}
      {p.satisfactionReport && p.latestScheme && (
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body p-4">
            <div className="font-bold mb-2">最新方案满意度</div>
            <div className="grid grid-cols-4 gap-3 text-center">
              <div><div className="text-2xl font-bold">{(p.avgSatisfaction * 100).toFixed(1)}%</div><div className="text-xs text-base-content/50">平均满意度</div></div>
              <div><div className="text-2xl font-bold text-error">{p.latestScheme.summary?.low_satisfaction_count || 0}</div><div className="text-xs text-base-content/50">低满意度教师</div></div>
              <div><div className="text-2xl font-bold">{p.latestScheme.item_count}</div><div className="text-xs text-base-content/50">排课片段</div></div>
              <div><div className="text-2xl font-bold">{p.latestScheme.profiled_teacher_count}</div><div className="text-xs text-base-content/50">画像教师数</div></div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div><label className="label pb-1 text-xs">搜索</label><input className="input input-bordered input-sm w-40" placeholder="姓名或ID" value={p.keyword} onChange={e => p.setKeyword(e.target.value)} /></div>
        <div><label className="label pb-1 text-xs">声明画像</label><select className="select select-bordered select-xs" value={p.declaredFilter} onChange={e => p.setDeclaredFilter(e.target.value)}><option value="all">全部</option><option value="yes">有</option><option value="no">无</option></select></div>
        <div><label className="label pb-1 text-xs">反馈画像</label><select className="select select-bordered select-xs" value={p.feedbackFilter} onChange={e => p.setFeedbackFilter(e.target.value)}><option value="all">全部</option><option value="yes">有</option><option value="no">无</option></select></div>
        {p.satisfactionReport && <div><label className="label pb-1 text-xs">满意度</label><select className="select select-bordered select-xs" value={p.satisfactionFilter} onChange={e => p.setSatisfactionFilter(e.target.value)}><option value="all">全部</option><option value="low">低满意度</option></select></div>}
        <div><label className="label pb-1 text-xs">标签</label><select className="select select-bordered select-xs" value={p.tagFilter} onChange={e => p.setTagFilter(e.target.value)}><option value="all">全部</option><option value="early">避早课</option><option value="late">避晚课</option></select></div>
      </div>

      {/* Profiles table */}
      <div className="overflow-x-auto">
        <table className="table table-zebra table-sm">
          <thead><tr><th>姓名</th><th>观测数</th><th>声明</th><th>反馈</th><th>置信度</th><th>避早课</th><th>避晚课</th><th>紧凑度</th><th>操作</th></tr></thead>
          <tbody>
            {p.loading ? <tr><td colSpan={9} className="text-center py-8"><span className="loading loading-spinner" /></td></tr>
            : p.filtered.length === 0 ? <tr><td colSpan={9} className="text-center py-8 text-base-content/40">暂无数据</td></tr>
            : p.filtered.map((prof, i) => <tr key={i}>
              <td>{prof.teacher_name}</td><td>{prof.observation_count}</td>
              <td><span className={`badge badge-xs ${prof.declared_profile ? "badge-success" : "badge-ghost"}`}>{prof.declared_profile ? "有" : "无"}</span></td>
              <td><span className={`badge badge-xs ${prof.feedback_profile ? "badge-info" : "badge-ghost"}`}>{prof.feedback_profile ? "有" : "无"}</span></td>
              <td>{prof.feedback_confidence != null ? (prof.feedback_confidence * 100).toFixed(0) + "%" : "-"}</td>
              <td>{prof.final_profile?.avoid_early_period ? "✅" : "—"}</td>
              <td>{prof.final_profile?.avoid_late_period ? "✅" : "—"}</td>
              <td>{prof.derived_from_data?.compactness_score != null ? prof.derived_from_data.compactness_score.toFixed(2) : "-"}</td>
              <td><button className="btn btn-xs btn-ghost" onClick={() => p.openDetail(prof)}>详情</button></td>
            </tr>)}
          </tbody>
        </table>
      </div>

      {/* Detail modal */}
      {p.detailVisible && p.selectedProfile && (
        <div className="modal modal-open">
          <div className="modal-box max-w-lg">
            <div className="flex justify-between items-center mb-4"><h3 className="font-bold text-lg">{p.selectedProfile.teacher_name}</h3><button className="btn btn-sm btn-ghost" onClick={() => p.setDetailVisible(false)}>关闭</button></div>
            <div className="space-y-3">
              {p.selectedProfile.declared_profile?.profile_note && <div className="p-3 bg-base-200 rounded text-sm">{p.selectedProfile.declared_profile.profile_note}</div>}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-base-content/50">避早课：</span>{p.selectedProfile.final_profile?.avoid_early_period ? "是" : "否"}</div>
                <div><span className="text-base-content/50">避晚课：</span>{p.selectedProfile.final_profile?.avoid_late_period ? "是" : "否"}</div>
                <div><span className="text-base-content/50">紧凑排课：</span>{p.selectedProfile.final_profile?.prefer_compact_schedule ? "是" : "否"}</div>
                <div><span className="text-base-content/50">置信度：</span>{p.selectedProfile.feedback_confidence != null ? (p.selectedProfile.feedback_confidence * 100).toFixed(0) + "%" : "—"}</div>
                <div><span className="text-base-content/50">日均课时：</span>{p.selectedProfile.derived_from_data?.avg_daily_lessons ?? "-"}</div>
                <div><span className="text-base-content/50">紧凑度分：</span>{p.selectedProfile.derived_from_data?.compactness_score?.toFixed(2) ?? "-"}</div>
                <div className="col-span-2"><span className="text-base-content/50">偏好周几：</span>{p.selectedProfile.final_profile?.preferred_weekdays?.join(", ") || "-"}</div>
                <div className="col-span-2"><span className="text-base-content/50">偏好教室：</span>{p.selectedProfile.final_profile?.preferred_room_types?.join(", ") || "-"}</div>
              </div>
              {p.selectedProfile.derived_from_data?.weekday_rates && <div className="space-y-1"><div className="text-sm font-medium">工作日偏好</div>{Object.entries(p.selectedProfile.derived_from_data.weekday_rates as Record<string, number>).map(([k,v]) => <RateBar key={k} rate={v} label={`周${k}`} />)}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
