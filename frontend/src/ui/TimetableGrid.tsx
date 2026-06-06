import type { Assignment } from "../hooks/useTimetable";

interface Props {
  loading: boolean;
  currentWeek: number;
  allWeeks: number[];
  weekItems: Assignment[];
  dayNames: string[];
  itemsAtSlot: (day: number, period: number) => Assignment[];
  onWeekChange: (w: number) => void;
}

export default function TimetableGrid({ loading, currentWeek, allWeeks, weekItems, dayNames, itemsAtSlot, onWeekChange }: Props) {
  return (
    <div>
      {loading ? <div className="text-center py-8"><span className="loading loading-spinner" /></div> : <>
        <div className="flex items-center gap-2 mb-4">
          <button className="btn btn-xs" disabled={currentWeek <= 1} onClick={() => onWeekChange(currentWeek - 1)}>‹ 上一周</button>
          <select className="select select-bordered select-xs w-28" value={currentWeek} onChange={e => onWeekChange(Number(e.target.value))}>
            {allWeeks.map(w => <option key={w} value={w}>第 {w} 周</option>)}
          </select>
          <button className="btn btn-xs" disabled={currentWeek >= 18} onClick={() => onWeekChange(currentWeek + 1)}>下一周 ›</button>
          <span className="text-sm text-base-content/50 ml-2">（第 {currentWeek} 周，{weekItems.length} 个排课片段）</span>
        </div>
        <div className="overflow-x-auto">
          <table className="table table-sm border-collapse">
            <thead>
              <tr>
                <th className="text-center bg-base-200 w-[60px]">节次</th>
                {dayNames.map(d => <th key={d} className="text-center bg-base-200 min-w-[100px]">{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3, 4, 5].map(period => (
                <tr key={period}>
                  <td className="text-center font-medium bg-base-200">第{period}节</td>
                  {[1, 2, 3, 4, 5, 6, 7].map(day => {
                    const items = itemsAtSlot(day, period);
                    return (
                      <td key={day} className="p-1 align-top min-h-[60px] border border-base-300">
                        {items.length > 0 ? (
                          <div className="flex flex-col gap-0.5">
                            {items.map(item => (
                              <div key={item.id} className="px-1 py-0.5 rounded text-xs bg-primary/10 text-primary">
                                <div className="font-semibold">{item.courseName}</div>
                                <div className="text-base-content/60">{item.classroomName} · {item.teacherName}</div>
                                <div className="text-base-content/40 text-[10px]">{item.classGroupName}</div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center text-base-content/20 text-xs leading-[60px]">空</div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>}
    </div>
  );
}
