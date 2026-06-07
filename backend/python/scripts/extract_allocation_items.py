#!/usr/bin/env python3
"""
从 schema01/ 的 Excel 课表中提取每一条排课记录（即每一个(周, 天, 节次)的片段）。
输出 allocation_items.jsonl，每条包含：
  course_code, teacher_name, class_group_name, week, day_of_week, period_index, room_name
"""

import json, re, sys
from collections import Counter
from pathlib import Path
import xlrd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "schema01"
OUT_DIR  = Path(__file__).resolve().parents[2] / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_title(row0):
    m = re.search(r'(\d{4}级.+?\d+班)', row0)
    return m.group(1) if m else ""

def extract_detail_courses(text):
    results = {}
    for m in re.finditer(r'(.+?)\(([^)]+)\)\(ID\[\d+\]学分\[([^\]]*)\]\s*时\[([^\]]*)\]\s*师\[([^\]]*)\]\s*室\[([^\]]*)\]', text):
        code = m.group(2).strip()
        teachers = [t.strip() for t in m.group(5).split(",") if t.strip()]
        if code:
            results[code] = teachers
    return results

def parse_cell(val):
    if not val or not isinstance(val, str): return None
    cell = val.strip()
    if not cell: return None
    skip = {"报到注册","国庆节","中秋节","元旦节","期末考试","全国计算机等级考试","大学英语四、六级考试","入学教育","军训","毕业教育","实践周","运动会"}
    if cell in skip or "报到" in cell or "节" in cell or "考试" in cell:
        return None
    parts = cell.split("\n")
    code = parts[0].strip()
    code_clean = re.sub(r'\(\d+[-\d,]*\)', "", code).strip()
    if not code_clean: return None
    room = ""
    for p in parts[1:]:
        p = p.strip()
        if p and p not in skip: room = p; break
    return (code_clean, room)

def main():
    print("="*50)
    print("提取真实课表排课片段")
    print("="*50)

    xls_files = sorted(DATA_DIR.glob("*.xls"))
    print(f"课表文件: {len(xls_files)}")

    items = []
    detail_teacher_map = {}

    for fpath in xls_files:
        wb = xlrd.open_workbook(str(fpath))
        sheet = wb.sheet_by_index(0)
        if sheet.nrows < 25: continue

        title = str(sheet.cell_value(0, 0) or "")
        cls_name = parse_title(title)
        if not cls_name: continue

        # Row 24 → teacher per course
        detail_text = str(sheet.cell_value(24, 0) or "")
        for code, teachers in extract_detail_courses(detail_text).items():
            if code not in detail_teacher_map:
                detail_teacher_map[code] = teachers

        # Schedule rows (4-23)
        for r in range(4, min(24, sheet.nrows - 1)):
            week = int(float(sheet.cell_value(r, 0))) if sheet.cell_value(r, 0) else 0
            if week <= 0 or week > 20: continue

            for col in range(2, sheet.ncols):
                parsed = parse_cell(str(sheet.cell_value(r, col)))
                if not parsed: continue
                code, room = parsed
                day = (col - 2) // 5 + 1
                period = (col - 2) % 5 + 1

                teacher_list = detail_teacher_map.get(code, [])
                teacher = teacher_list[0] if teacher_list else ""

                items.append({
                    "course_code": code,
                    "teacher_name": teacher,
                    "class_group_name": cls_name,
                    "week": week,
                    "day_of_week": day,
                    "period_index": period,
                    "room_name": room,
                })

    print(f"总排课片段: {len(items)}")

    # 输出
    out_path = OUT_DIR / "allocation_items.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"输出: {out_path}")

    # 快速分析
    print("\n" + "="*50)
    print("快速分析")
    print("="*50)

    # 不同 (天, 节次) 组合数
    slot_items = [(it["day_of_week"], it["period_index"]) for it in items]
    unique_slots = len(set(slot_items))
    print(f"不同 (天, 节次) 组合: {unique_slots}")

    # 不同教室数
    rooms = set(it["room_name"] for it in items)
    print(f"不同教室: {len(rooms)}")

    # 不同 (教室, 天, 节次) 组合数
    full_slots = set((it["room_name"], it["day_of_week"], it["period_index"]) for it in items)
    print(f"不同 (教室, 天, 节次) 组合: {len(full_slots)}")

    # 热度分布
    slot_counter = Counter(slot_items)
    print(f"\n热度 Top 10 (天, 节次):")
    for (d, p), c in slot_counter.most_common(10):
        day_name = ["", "周一","周二","周三","周四","周五","周六","周日"][d]
        print(f"  {day_name} 第{p}节: {c} 次 ({c/len(items)*100:.1f}%)")

    # 每个 slot 的教室多样性
    slot_room_counts = Counter()
    for item in items:
        slot_room_counts[(item["day_of_week"], item["period_index"], item["room_name"])] += 1
    print(f"\n不同 (天, 节次, 教室) 组合: {len(slot_room_counts)}")
    print(f"总排课数 / 组合数 = {len(items)} / {len(slot_room_counts)} = {len(items)/max(1,len(slot_room_counts)):.2f}")

    # 课时最多的老师
    teacher_counts = Counter(it["teacher_name"] for it in items if it["teacher_name"])
    print(f"\n教师排课量 Top 5:")
    for t, c in teacher_counts.most_common(5):
        print(f"  {t}: {c} 个片段")

if __name__ == "__main__":
    main()
