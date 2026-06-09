import { Link, useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import request from "../api/request";
import {
  ConflictDetails,
  filterSchemeItems,
  SchemeItemsTable,
  SchemeTimetable,
  uniqueOptions,
} from "../components/SchemeDetailView";
import type { AllocationScheme, SchemeItem } from "../hooks/useAllocation";

export default function AllocationSchemeDetailPage() {
  const { schemeId } = useParams({ from: "/admin/allocation/schemes/$schemeId" });
  const [scheme, setScheme] = useState<AllocationScheme | null>(null);
  const [items, setItems] = useState<SchemeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedConflictId, setSelectedConflictId] = useState<number | null>(null);
  const [teacher, setTeacher] = useState("");
  const [classGroup, setClassGroup] = useState("");
  const [classroom, setClassroom] = useState("");
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    let canceled = false;
    async function load() {
      setLoading(true);
      try {
        const [schemeData, itemData] = await Promise.all([
          request.get(`/api/allocation-schemes/${schemeId}`),
          request.get(`/api/allocation-schemes/${schemeId}/items`),
        ]);
        if (canceled) return;
        setScheme(schemeData as AllocationScheme);
        setItems(Array.isArray(itemData) ? itemData : []);
      } catch {
        if (canceled) return;
        setScheme(null);
        setItems([]);
      } finally {
        if (!canceled) setLoading(false);
      }
    }
    load();
    return () => { canceled = true; };
  }, [schemeId]);

  const teacherOptions = useMemo(() => uniqueOptions(items, "teacherName"), [items]);
  const classOptions = useMemo(() => uniqueOptions(items, "classGroupName"), [items]);
  const classroomOptions = useMemo(() => uniqueOptions(items, "classroomName"), [items]);
  const filteredItems = useMemo(
    () => filterSchemeItems(items, { teacher, classGroup, classroom, keyword }),
    [items, teacher, classGroup, classroom, keyword],
  );
  const conflictCount = filteredItems.filter(item => item.valid === false).length;
  const hasFilter = teacher || classGroup || classroom || keyword;

  const stats = {
    totalItems: items.length,
    conflicts: items.filter(i => i.valid === false).length,
    conflictRate: items.length ? (items.filter(i => i.valid === false).length / items.length * 100).toFixed(1) : "0",
    courses: new Set(items.map(i => i.courseName)).size,
    teachers: new Set(items.map(i => i.teacherName)).size,
    classes: new Set(items.map(i => i.classGroupName)).size,
    weeks: new Set(items.map(i => i.weekNumber)).size,
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-base-content/50 mb-1">
            <Link to="/admin/allocation" className="link link-hover">分课任务</Link>
            <span>/</span>
            <span>方案详情</span>
          </div>
          <h2 className="text-xl font-semibold tracking-tight">{scheme?.name || `方案 #${schemeId}`}</h2>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            {scheme?.schemeScore != null && <span className="badge badge-outline badge-info font-mono">评分 {scheme.schemeScore.toFixed(4)}</span>}
            {scheme?.status && <span className="badge badge-outline">{scheme.status}</span>}
            <span className="badge badge-ghost">{filteredItems.length} / {items.length} 条记录</span>
            {conflictCount > 0 && <span className="badge badge-error">{conflictCount} 个冲突</span>}
          </div>
        </div>
        <Link to="/admin/allocation" className="btn btn-sm btn-ghost">返回方案列表</Link>
      </div>

      {/* Quality metrics */}
      {!loading && items.length > 0 && (
        <div className="flex flex-wrap items-stretch gap-3">
          <div className="stat bg-base-100 border border-base-300 rounded-lg p-3 min-w-[100px] flex-1">
            <div className="stat-title text-xs text-base-content/60">已排记录</div>
            <div className="stat-value text-lg text-primary">{stats.totalItems}</div>
            <div className="stat-desc text-[10px] text-base-content/40">{stats.weeks} 周 · {stats.courses} 门课程</div>
          </div>
          <div className="stat bg-base-100 border border-base-300 rounded-lg p-3 min-w-[100px] flex-1">
            <div className="stat-title text-xs text-base-content/60">冲突</div>
            <div className={`stat-value text-lg ${stats.conflicts > 0 ? "text-error" : "text-success"}`}>
              {stats.conflicts}
              <span className="text-sm font-normal ml-1 text-base-content/40">({stats.conflictRate}%)</span>
            </div>
            <div className="stat-desc text-[10px] text-base-content/40">{stats.conflicts > 0 ? "需要人工处理" : "无冲突"}</div>
          </div>
          <div className="stat bg-base-100 border border-base-300 rounded-lg p-3 min-w-[100px] flex-1">
            <div className="stat-title text-xs text-base-content/60">教师</div>
            <div className="stat-value text-lg text-info">{stats.teachers}</div>
            <div className="stat-desc text-[10px] text-base-content/40">涉及教师数</div>
          </div>
          <div className="stat bg-base-100 border border-base-300 rounded-lg p-3 min-w-[100px] flex-1">
            <div className="stat-title text-xs text-base-content/60">班级</div>
            <div className="stat-value text-lg text-accent">{stats.classes}</div>
            <div className="stat-desc text-[10px] text-base-content/40">覆盖班级数</div>
          </div>
          <div className="stat bg-base-100 border border-base-300 rounded-lg p-3 min-w-[100px] flex-1">
            <div className="stat-title text-xs text-base-content/60">冲突率</div>
            <div className={`stat-value text-lg ${stats.conflicts > 0 ? "text-warning" : "text-success"}`}>{stats.conflictRate}%</div>
            <div className="stat-desc text-[10px] text-base-content/40">{stats.conflicts > 0 ? `${stats.conflicts} / ${stats.totalItems}` : "全量通过"}</div>
          </div>
        </div>
      )}

      <div className="card bg-base-100 shadow-sm border border-base-300">
        <div className="card-body p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">关键词</span></div>
              <input className="input input-sm input-bordered" placeholder="课程 / 教师 / 班级 / 教室" value={keyword} onChange={event => setKeyword(event.target.value)} />
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">教师</span></div>
              <select className="select select-sm select-bordered" value={teacher} onChange={event => setTeacher(event.target.value)}>
                <option value="">全部教师</option>
                {teacherOptions.map(option => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">班级</span></div>
              <select className="select select-sm select-bordered" value={classGroup} onChange={event => setClassGroup(event.target.value)}>
                <option value="">全部班级</option>
                {classOptions.map(option => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="form-control">
              <div className="label py-1"><span className="label-text text-xs text-base-content/60">教室</span></div>
              <select className="select select-sm select-bordered" value={classroom} onChange={event => setClassroom(event.target.value)}>
                <option value="">全部教室</option>
                {classroomOptions.map(option => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <div className="flex items-end">
              <button className="btn btn-sm btn-outline w-full" disabled={!hasFilter} onClick={() => { setTeacher(""); setClassGroup(""); setClassroom(""); setKeyword(""); }}>
                清空筛选
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24"><span className="loading loading-spinner loading-lg text-primary" /></div>
      ) : items.length === 0 ? (
        <div className="flex items-center justify-center py-24 text-base-content/30 font-medium">暂无排课明细数据</div>
      ) : filteredItems.length === 0 ? (
        <div className="flex items-center justify-center py-24 text-base-content/30 font-medium">没有匹配当前筛选条件的记录</div>
      ) : (
        <div className="space-y-5">
          <SchemeTimetable items={filteredItems} selectedConflictId={selectedConflictId} onConflictClick={item => setSelectedConflictId(selectedConflictId === item.id ? null : item.id)} />
          <details className="collapse collapse-arrow border border-base-300 rounded-lg bg-base-100">
            <summary className="collapse-title text-sm font-medium text-base-content/70">列表视图（{filteredItems.length} 条）</summary>
            <div className="collapse-content p-0"><SchemeItemsTable items={filteredItems} /></div>
          </details>
          <ConflictDetails items={filteredItems} selectedConflictId={selectedConflictId} onSelect={setSelectedConflictId} />
        </div>
      )}
    </div>
  );
}
