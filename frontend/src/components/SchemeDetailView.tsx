import { useMemo, useState } from "react";
import type { SchemeItem } from "../hooks/useAllocation";

const RAINBOW_HUES = [0, 20, 45, 80, 140, 175, 200, 230, 260, 290, 320, 345];
const DAY_LABELS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const PERIOD_LABELS = ["第1节", "第2节", "第3节", "第4节", "第5节"];

function taskKey(item: SchemeItem) {
  return `${item.courseName ?? ""}|${item.teacherName ?? ""}|${item.classGroupName ?? ""}`;
}

function buildHueMap(items: SchemeItem[]) {
  const keys = [...new Set(items.map(taskKey))].sort();
  const hueMap = new Map<string, number>();
  keys.forEach((key, index) => hueMap.set(key, RAINBOW_HUES[index % RAINBOW_HUES.length]));
  return hueMap;
}

export function uniqueOptions(items: SchemeItem[], key: keyof SchemeItem) {
  return [...new Set(items.map(item => String(item[key] ?? "").trim()).filter(Boolean))].sort();
}

export function filterSchemeItems(
  items: SchemeItem[],
  filters: { teacher?: string; classGroup?: string; classroom?: string; keyword?: string },
) {
  const keyword = filters.keyword?.trim().toLowerCase();
  return items.filter(item => {
    if (filters.teacher && item.teacherName !== filters.teacher) return false;
    if (filters.classGroup && item.classGroupName !== filters.classGroup) return false;
    if (filters.classroom && item.classroomName !== filters.classroom) return false;
    if (!keyword) return true;
    return [item.courseName, item.teacherName, item.classGroupName, item.classroomName]
      .some(value => String(value ?? "").toLowerCase().includes(keyword));
  });
}

export function SchemeTimetable({
  items,
  selectedConflictId,
  onConflictClick,
}: {
  items: SchemeItem[];
  selectedConflictId?: number | null;
  onConflictClick?: (item: SchemeItem) => void;
}) {
  const [week, setWeek] = useState(0);
  const allWeeks = [...new Set(items.map(item => item.weekNumber))].sort((a, b) => a - b);
  const currentWeek = week && allWeeks.includes(week) ? week : allWeeks[0] || 0;
  const weekItems = items.filter(item => item.weekNumber === currentWeek);
  const hueMap = useMemo(() => buildHueMap(items), [items]);

  const days = [1, 2, 3, 4, 5, 6, 7];
  const periods = [1, 2, 3, 4, 5];
  const slotMap = new Map<string, SchemeItem[]>();
  for (const item of weekItems) {
    const key = `${item.dayOfWeek}-${item.periodIndex}`;
    if (!slotMap.has(key)) slotMap.set(key, []);
    slotMap.get(key)!.push(item);
  }

  return (
    <div>
      {allWeeks.length > 1 && (
        <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1">
          <span className="text-xs text-base-content/40 font-medium shrink-0">周次</span>
          <div className="join">
            {allWeeks.map(weekNumber => (
              <button
                key={weekNumber}
                className={`join-item btn btn-xs min-w-8 ${weekNumber === currentWeek ? "btn-active btn-primary text-primary-content" : "btn-ghost text-base-content/60"}`}
                onClick={() => setWeek(weekNumber)}
              >
                {weekNumber}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-base-300 bg-base-100">
        <table className="table table-sm w-full">
          <thead>
            <tr className="bg-base-200/50">
              <th className="w-16 text-xs font-medium text-base-content/50 text-center">节次</th>
              {days.map(day => (
                <th key={day} className={`text-center text-xs font-medium min-w-36 px-1 ${day >= 6 ? "text-warning/60" : "text-base-content/50"}`}>
                  {DAY_LABELS[day]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map(period => (
              <tr key={period} className="border-t border-base-200/50">
                <td className="text-xs text-base-content/40 text-center font-mono px-1 py-0.5 align-top leading-[72px]">
                  {PERIOD_LABELS[period - 1]}
                </td>
                {days.map(day => {
                  const slotItems = slotMap.get(`${day}-${period}`);
                  return (
                    <td key={day} className="p-1 align-top min-h-[72px]">
                      {slotItems?.map(item => {
                        const hue = hueMap.get(taskKey(item)) ?? 0;
                        return (
                          <div
                            key={item.id}
                            className={`text-[11px] leading-snug mb-1 p-2 rounded-md border-l-[3px] transition-all ${selectedConflictId === item.id ? "ring-2 ring-error ring-offset-1" : ""} ${item.valid !== false ? "text-base-content" : "text-error cursor-pointer hover:brightness-110"}`}
                            style={{
                              borderLeftColor: item.valid !== false ? `hsl(${hue}, 65%, 50%)` : undefined,
                              backgroundColor: item.valid !== false ? `hsla(${hue}, 65%, 50%, 0.1)` : undefined,
                            }}
                            onClick={() => item.valid === false && onConflictClick?.(item)}
                            title={item.conflictMessage || ""}
                          >
                            {item.valid === false && (
                              <div className="flex items-center gap-1 mb-0.5">
                                <span className="inline-block w-1.5 h-1.5 rounded-full bg-error animate-pulse" />
                                <span className="text-[9px] uppercase tracking-wider font-semibold">冲突</span>
                              </div>
                            )}
                            <div className="font-semibold truncate" style={{ color: `hsl(${hue}, 65%, 60%)` }}>{item.courseName || "-"}</div>
                            <div className="text-[10px] text-base-content/60 truncate">{item.classGroupName || "-"}</div>
                            <div className="text-[10px] text-base-content/40 truncate">{item.classroomName || "-"} · {item.teacherName || "-"}</div>
                          </div>
                        );
                      })}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SchemeItemsTable({ items }: { items: SchemeItem[] }) {
  const hueMap = useMemo(() => buildHueMap(items), [items]);
  return (
    <div className="overflow-x-auto rounded-lg border border-base-300">
      <table className="table table-sm">
        <thead>
          <tr className="text-xs text-base-content/50 uppercase tracking-wider">
            <th className="font-medium w-2"></th>
            <th className="font-medium">周次</th>
            <th className="font-medium">星期</th>
            <th className="font-medium">节次</th>
            <th className="font-medium">课程</th>
            <th className="font-medium">教师</th>
            <th className="font-medium">班级</th>
            <th className="font-medium">教室</th>
            <th className="font-medium">评分</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => {
            const hue = hueMap.get(taskKey(item)) ?? 0;
            return (
              <tr key={item.id} className={`text-sm transition-colors ${item.valid === false ? "bg-error/5" : ""}`}>
                <td className="w-3 px-0">
                  {item.valid !== false && <span className="inline-block w-full h-full min-h-[1.5rem]" style={{ backgroundColor: `hsl(${hue}, 65%, 50%)` }}>&nbsp;</span>}
                </td>
                <td className="font-mono text-xs">{item.weekNumber}</td>
                <td>{DAY_LABELS[item.dayOfWeek] || item.dayOfWeek}</td>
                <td className="font-mono text-xs">第{item.periodIndex}节</td>
                <td className="font-medium">{item.courseName || "-"}</td>
                <td className="text-base-content/70">{item.teacherName || "-"}</td>
                <td className="text-base-content/70">{item.classGroupName || "-"}</td>
                <td className="text-base-content/70 font-mono text-xs">{item.classroomName || "-"}</td>
                <td className="font-mono text-xs text-right">{item.teacherProfileScore != null ? item.teacherProfileScore.toFixed(2) : "-"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ConflictDetails({
  items,
  selectedConflictId,
  onSelect,
}: {
  items: SchemeItem[];
  selectedConflictId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const conflictItems = items.filter(item => item.valid === false);
  const hueMap = useMemo(() => buildHueMap(items), [items]);
  if (conflictItems.length === 0) return null;

  return (
    <details className="collapse collapse-arrow border border-error/30 rounded-lg bg-error/[0.03]" open>
      <summary className="collapse-title text-sm font-medium text-error flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-error" />
        冲突详情（{conflictItems.length} 项）
      </summary>
      <div className="collapse-content p-0">
        <div className="divide-y divide-error/10">
          {conflictItems.map(item => {
            const isSelected = selectedConflictId === item.id;
            const hue = hueMap.get(taskKey(item)) ?? 0;
            return (
              <div
                key={item.id}
                className={`px-4 py-3 flex items-start gap-3 cursor-pointer transition-colors ${isSelected ? "bg-error/[0.08]" : "hover:bg-error/[0.04]"}`}
                onClick={() => onSelect(isSelected ? null : item.id)}
              >
                <div className="w-1 h-full min-h-[3rem] shrink-0 rounded-full mt-0.5" style={{ backgroundColor: `hsl(${hue}, 65%, 50%)` }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-sm flex-wrap">
                    <span className="font-semibold">{item.courseName || "-"}</span>
                    <span className="text-base-content/50">·</span>
                    <span className="text-base-content/60 text-xs">{item.teacherName || "-"}</span>
                    <span className="text-base-content/50">·</span>
                    <span className="text-base-content/60 text-xs">{item.classGroupName || "-"}</span>
                  </div>
                  <div className="text-xs text-base-content/40 mt-0.5">
                    第{item.weekNumber}周 {DAY_LABELS[item.dayOfWeek] || item.dayOfWeek} 第{item.periodIndex}节 · {item.classroomName || "-"}
                  </div>
                  <div className="flex items-start gap-1.5 mt-2 p-2 rounded bg-error/[0.06] text-xs text-error">
                    <span>{item.conflictMessage || "未知冲突"}</span>
                  </div>
                </div>
                {isSelected && <span className="text-xs text-error font-medium shrink-0">查看中</span>}
              </div>
            );
          })}
        </div>
      </div>
    </details>
  );
}
