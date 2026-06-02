#!/usr/bin/env python3
"""
全校课表批量解析脚本
输入：2025-2026学年1学期总课表/ 下的 *.xls 文件
输出：data/real-dataset/ 下的结构化 JSON + CSV

用法：python3 scripts/parse_timetables.py
"""

import xlrd
import re
import json
import os
import csv
import sys
from pathlib import Path

# ── 配置 ─────────────────────────────────────────────
INPUT_DIR = Path.home() / "Downloads" / "2025-2026学年1学期总课表"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "real-dataset"
# ────────────────────────────────────────────────────

# 星期映射
DAY_MAP = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}  # col group index → day (1=Mon)
PERIOD_MAP = {0: "1-2", 1: "3-4", 2: "5-6", 3: "7-8", 4: "9-11"}  # group → period label
PERIOD_START = {0: 1, 1: 3, 2: 5, 3: 7, 4: 9}

# ── 文件名解析 ────────────────────────────────────────
def parse_filename(fname: str) -> dict:
    """从文件名提取年级、专业、班级"""
    # 标准格式: 2023级软件工程2班课表_xxx.xls
    # 特殊格式: 2024级工商管理（国际）班课表_xxx.xls（无班号）
    m = re.search(r'(\d{4})级(.+?)班', fname)
    if not m:
        return {"grade": "?", "major": "?", "class_no": "?"}
    
    major_part = m.group(2).strip()  # e.g. "软件工程2" or "工商管理（国际）"
    # 提取班号：最后连续数字
    num_m = re.search(r'(\d+)$', major_part)
    if num_m:
        class_no = int(num_m.group(1))
        major = major_part[:-len(num_m.group(1))].strip()
    else:
        class_no = 1  # 无班号默认1班
        major = major_part
    
    return {
        "grade": int(m.group(1)),
        "major": major,
        "class_no": class_no,
    }


# ── 单文件解析 ────────────────────────────────────────
def parse_one_xls(path: Path) -> dict:
    """解析一个课表 xls，返回结构化数据"""
    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)

    meta = parse_filename(path.name)
    title = str(ws.cell_value(0, 0))

    # 从标题提取院系（去掉学期前缀）
    dept_m = re.search(r'第\d+学期(.+?系\(学院\))', title)
    if not dept_m:
        dept_m = re.search(r'(.+?系\(学院\))', title)
    meta["department"] = dept_m.group(1) if dept_m else ""

    # ── 课程汇总信息（最后一行） ──
    summary = str(ws.cell_value(ws.nrows - 2, 0))
    
    # 解析所有课程
    # 格式：课程名(代码)(ID[id]学分[学分]) 时[学时] 师[教师1,教师2] 室[教室1,教室2]
    course_pattern = re.compile(
        r'([\u4e00-\u9fa5]+)\(([^)]+?)\)\(ID\[\d+\]学分\[([\d.]+)\]\)\s+'
        r'时\[([\d.]+)\]\s+师\[([^\]]+)\]\s+室\[([^\]]+)\]'
    )
    courses_raw = course_pattern.findall(summary)

    courses = []
    for c in courses_raw:
        name, code, credits, hours, teachers, rooms = c
        teacher_list = [t.strip() for t in re.split(r'[,，]', teachers) if t.strip()]
        room_list = [r.strip() for r in re.split(r'[,，]', rooms.replace(" ", "")) if r.strip()]
        courses.append({
            "name": name,
            "code": code,
            "credits": float(credits),
            "hours": float(hours),
            "teachers": teacher_list,
            "rooms": room_list,
        })

    # ── 排课明细（周次 × 天 × 节次） ──
    timetable = []
    
    # 表头在 row 2（天）和 row 3（节次组）
    # 从 row 4 开始是第 1 周，到 row 23 是第 20 周（或 19 周）
    for r in range(4, min(ws.nrows - 2, 4 + 20)):  # 最多 20 周
        week_val = ws.cell_value(r, 0)
        try:
            week = int(float(week_val))
        except (ValueError, TypeError):
            continue
        
        # 日期字符串（col 1）
        date_str = str(ws.cell_value(r, 1)).strip()
        
        # col 2-36: 周一(2-6) ~ 周日(32-36), 每组 5 列
        for c in range(2, ws.ncols):
            val = str(ws.cell_value(r, c)).strip()
            if not val or val in ["报到注册", "期末考试", "清明节", "五一节", "国庆节", ""]:
                continue
            
            day_idx = (c - 2) // 5  # 0=周一, 6=周日
            period_idx = (c - 2) % 5  # 0=1-2节, 4=9-11节
            day = DAY_MAP.get(day_idx, day_idx + 1)
            period_label = PERIOD_MAP.get(period_idx, f"{period_idx+1}")
            
            lines = val.split('\n')
            course_code = lines[0].strip() if lines else val
            room_code = lines[1].strip() if len(lines) >= 2 else ""
            
            entry = {
                "week": week,
                "day": day,
                "period_label": period_label,
                "period_start": PERIOD_START.get(period_idx, 1),
                "course_code": course_code,
                "room": room_code,
            }
            timetable.append(entry)

    return {
        "meta": meta,
        "title": title,
        "courses": courses,
        "timetable": timetable,
    }


# ── 数据收集和去重 ────────────────────────────────────
def collect_all():
    """遍历所有 xls，收集汇总数据"""
    xls_files = sorted(INPUT_DIR.glob("*.xls"))
    if not xls_files:
        print(f"❌ 在 {INPUT_DIR} 下没有找到 .xls 文件")
        sys.exit(1)
    
    print(f"📂 找到 {len(xls_files)} 个课表文件，开始解析...\n")
    
    all_teachers = {}       # name -> {departments, courses}
    all_classrooms = {}     # room -> {courses_used_in}
    all_courses = {}        # code -> {name, credits, hours, teachers, rooms, classes}
    all_class_groups = []   # list of {grade, major, class_no, department}
    all_teaching_tasks = []  # list of {course, teacher, class, hours, rooms, semester}
    _seen_tt = set()          # dedup: (course_code, class_group)
    all_timetables = []      # list of {class, course, week, day, period, room}

    semester = "2025-2026-1"  # 当前总课表学期
    
    warnings = []  # Data quality warnings

    for fi, path in enumerate(xls_files):
        if (fi + 1) % 100 == 0:
            print(f"  进度: {fi+1}/{len(xls_files)}...")
        
        try:
            data = parse_one_xls(path)
        except Exception as e:
            print(f"  ⚠️ 解析失败: {path.name} — {e}")
            continue
        
        meta = data["meta"]
        
        # 校验：文件名解析异常
        if meta["grade"] == "?":
            print(f"  ⚠️ 文件名解析失败: {path.name}")
            continue
        
        # 班级信息
        class_key = f"{meta['grade']}级{meta['major']}{meta['class_no']}班"
        
        # 校验：学生数异常
        stu_cnt = extract_student_count(data["title"])
        if 0 < stu_cnt < 5:
            warnings.append(f"   ⚠️ 学生数异常: {class_key} — {stu_cnt}人 (数据确认中)")
        
        # 校验：课程数为0
        if len(data["courses"]) == 0:
            warnings.append(f"   ⚠️ 课程数为0: {class_key}")
        all_class_groups.append({
            "key": class_key,
            "grade": meta["grade"],
            "major": meta["major"],
            "class_no": meta["class_no"],
            "department": meta["department"],
            "student_count": extract_student_count(data["title"]),
        })
        
        # 课程 + 教师 + 教室
        for c in data["courses"]:
            code = c["code"]
            if code not in all_courses:
                all_courses[code] = {
                    "name": c["name"],
                    "code": code,
                    "credits": c["credits"],
                    "hours": c["hours"],
                    "teachers": [],
                    "rooms": set(),
                    "classes": [],
                }
            # 一个课程在不同班级的学分/学时应该一致，保留首次出现的值
            # （如果出现不一致说明数据有问题，首次值至少可溯源）
            
            for t in c["teachers"]:
                if t not in all_teachers:
                    all_teachers[t] = {"name": t, "departments": set(), "courses": []}
                all_teachers[t]["departments"].add(meta["department"])
                if code not in all_teachers[t]["courses"]:
                    all_teachers[t]["courses"].append(code)
                if t not in all_courses[code]["teachers"]:
                    all_courses[code]["teachers"].append(t)
            
            for r in c["rooms"]:
                all_courses[code]["rooms"].add(r)
                if r not in all_classrooms:
                    all_classrooms[r] = {"name": r, "courses": []}
                if code not in all_classrooms[r]["courses"]:
                    all_classrooms[r]["courses"].append(code)
            
            if class_key not in all_courses[code]["classes"]:
                all_courses[code]["classes"].append(class_key)
            
            # 教学任务：每门课+班级只一条，取第一位教师（教室由模型推荐）
            if (code, class_key) not in _seen_tt:
                _seen_tt.add((code, class_key))
                first_teacher = c["teachers"][0] if c["teachers"] else ""
                all_teaching_tasks.append({
                    "course_code": code,
                    "teacher": first_teacher,
                    "class_group": class_key,
                    "total_hours": c["hours"],
                })
        
        # 排课明细
        for entry in data["timetable"]:
            all_timetables.append({
                "class_group": class_key,
                "grade": meta["grade"],
                "major": meta["major"],
                "class_no": meta["class_no"],
                **entry,
            })
    
    # 去重教师课程列表
    for t_name, info in all_teachers.items():
        info["courses"] = list(set(info["courses"]))
        info["departments"] = list(info["departments"])
    
    # 去重教室课程列表
    for r_name, info in all_classrooms.items():
        info["courses"] = list(set(info["courses"]))
    
    # 转换 set → list
    for code, info in all_courses.items():
        info["rooms"] = list(info["rooms"])

    # 对 classrooms 做类型推断，用于后续 course_type 打标
    _infer_classroom_types(all_classrooms)

    # 对 courses 做类型推断
    _infer_course_types(all_courses, all_classrooms, all_teaching_tasks)

    print(f"\n✅ 解析完成！")
    if warnings:
        print(f"\n⚠️  数据校验告警（{len(warnings)} 条）：")
        for w in warnings:
            print(w)
    print(f"   {len(all_class_groups)} 个班级")
    print(f"   {len(all_courses)} 门课程")
    print(f"   {len(all_teachers)} 位教师")
    print(f"   {len(all_classrooms)} 间教室")
    print(f"   {len(all_teaching_tasks)} 条教学任务")
    print(f"   {len(all_timetables)} 条排课记录")
    
    return {
        "teachers": all_teachers,
        "classrooms": all_classrooms,
        "courses": all_courses,
        "class_groups": all_class_groups,
        "teaching_tasks": all_teaching_tasks,
        "timetables": all_timetables,
    }


def extract_student_count(title: str) -> int:
    m = re.search(r'共(\d+)人', title)
    return int(m.group(1)) if m else 0


# ── 类型推断（parse 阶段完成，不让脏数据流到 import） ──

def _classroom_type_from_name(name: str) -> str:
    """从房间号推断教室类型"""
    if not name:
        return "普通教室"
    if name[0].isdigit():
        if name.startswith("9"):
            return "机房"
        if name.startswith("0"):
            return "普通教室"
    if name.startswith("xn"):
        return "虚拟教室"
    if name.startswith("jjx"):
        return "阶梯教室"
    if any(kw in name for kw in ["操场", "球场", "攀岩", "轮滑", "乒乓"]):
        return "操场"
    if "形体" in name:
        return "形体教室"
    return "普通教室"


def _infer_classroom_types(classrooms: dict):
    """给所有教室打上类型标签"""
    for info in classrooms.values():
        info["classroom_type"] = _classroom_type_from_name(info["name"])


def _infer_course_types(courses: dict, classrooms: dict, teaching_tasks: list):
    """根据教学任务使用的教室类型推断课程类型"""
    # 统计每个 course 用到的 classroom_type
    course_room_map = {}  # course_code -> set of classroom_type
    for tt in teaching_tasks:
        code = tt["course_code"]
        if code not in course_room_map:
            course_room_map[code] = set()
        for room_name in (tt.get("rooms") or []):
            cr = classrooms.get(room_name)
            if cr:
                course_room_map[code].add(cr.get("classroom_type", "普通教室"))

    for code, info in courses.items():
        types = course_room_map.get(code, set())
        has_lab = "机房" in types
        has_regular = "普通教室" in types
        has_special = bool(types - {"机房", "普通教室"})

        if has_lab and not has_regular and not has_special:
            info["course_type"] = "上机课"
            info["required_room_type"] = "机房"
        elif has_regular and not has_lab and not has_special:
            info["course_type"] = "理论课"
            info["required_room_type"] = "普通教室"
        elif not types:
            # 没用到任何教室 → 按名称关键词补漏
            name = info.get("name", "")
            if any(kw in name for kw in ["上机", "实验", "实训"]):
                info["course_type"] = "上机课"
                info["required_room_type"] = "机房"
            elif any(kw in name for kw in ["实习", "实践", "军事", "校企", "工程素质"]):
                info["course_type"] = "实践课"
                info["required_room_type"] = None
            else:
                info["course_type"] = "理论课"
                info["required_room_type"] = "普通教室"
        else:
            # 混合/特殊 → 实践课
            info["course_type"] = "实践课"
            info["required_room_type"] = None


# ── 输出 ──────────────────────────────────────────────
def write_outputs(data: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. teachers.jsonl — 只保留下游消费的字段
    teachers_list = sorted(data["teachers"].values(), key=lambda x: x["name"])
    with open(OUTPUT_DIR / "teachers.jsonl", "w", encoding="utf-8") as f:
        for t in teachers_list:
            f.write(json.dumps({
                "name": t["name"],
                "departments": t["departments"],
            }, ensure_ascii=False) + "\n")
    print(f"  📄 teachers.jsonl — {len(teachers_list)} 人")

    # 2. classrooms.jsonl — 带上类型 + 容量（按类型固定）
    classrooms_list = sorted(data["classrooms"].values(), key=lambda x: x["name"])
    with open(OUTPUT_DIR / "classrooms.jsonl", "w", encoding="utf-8") as f:
        for r in classrooms_list:
            ctype = r.get("classroom_type", "普通教室")
            cap = {"普通教室": 80, "机房": 120, "阶梯教室": 200, "虚拟教室": 1200, "操场": 1000, "形体教室": 1000}
            f.write(json.dumps({
                "name": r["name"],
                "classroom_type": ctype,
                "capacity": cap.get(ctype, 80),
            }, ensure_ascii=False) + "\n")
    print(f"  📄 classrooms.jsonl — {len(classrooms_list)} 间")

    # 3. courses.jsonl — 带上课程类型 + 所需教室类型
    courses_list = sorted(data["courses"].values(), key=lambda x: x["code"])
    with open(OUTPUT_DIR / "courses.jsonl", "w", encoding="utf-8") as f:
        for c in courses_list:
            f.write(json.dumps({
                "name": c["name"],
                "code": c["code"],
                "credits": c["credits"],
                "hours": c["hours"],
                "course_type": c.get("course_type"),
                "required_room_type": c.get("required_room_type"),
            }, ensure_ascii=False) + "\n")
    print(f"  📄 courses.jsonl — {len(courses_list)} 门")

    # 4. class_groups.jsonl — 对齐 DB 字段
    with open(OUTPUT_DIR / "class_groups.jsonl", "w", encoding="utf-8") as f:
        for g in data["class_groups"]:
            f.write(json.dumps({
                "name": g["key"],
                "major": g.get("major", ""),
                "department": g.get("department", ""),
                "grade": str(g.get("grade", "")),
                "student_count": g.get("student_count", 0),
            }, ensure_ascii=False) + "\n")
    print(f"  📄 class_groups.jsonl — {len(data['class_groups'])} 个")

    # 5. teaching_tasks.jsonl
    with open(OUTPUT_DIR / "teaching_tasks.jsonl", "w", encoding="utf-8") as f:
        for tt in data["teaching_tasks"]:
            f.write(json.dumps(tt, ensure_ascii=False) + "\n")
    print(f"  📄 teaching_tasks.jsonl — {len(data['teaching_tasks'])} 条")
    
    # 6. timetables.jsonl (JSON Lines — 逐行可读，适合海量数据)
    with open(OUTPUT_DIR / "timetables.jsonl", "w", encoding="utf-8") as f:
        for entry in data["timetables"]:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  📄 timetables.jsonl — {len(data['timetables'])} 条")
    
    # 7. summary.csv
    with open(OUTPUT_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["班级", "年级", "专业", "班号", "人数", "院系", "课程数", "教师数"])
        
        # Group teaching tasks by class
        from collections import Counter
        tasks_by_class = {}
        for tt in data["teaching_tasks"]:
            ck = tt["class_group"]
            if ck not in tasks_by_class:
                tasks_by_class[ck] = {"courses": set(), "teachers": set()}
            tasks_by_class[ck]["courses"].add(tt["course_code"])
            tasks_by_class[ck]["teachers"].add(tt["teacher"])
        
        for cg in data["class_groups"]:
            ck = cg["key"]
            stats = tasks_by_class.get(ck, {"courses": set(), "teachers": set()})
            writer.writerow([
                ck, cg["grade"], cg["major"], cg.get("class_no", ""),
                cg.get("student_count", 0), cg.get("department", ""),
                len(stats["courses"]), len(stats["teachers"]),
            ])
    print(f"  📄 summary.csv — 汇总统计")
    
    print(f"\n📂 全部输出到: {OUTPUT_DIR}")


# ── 主入口 ────────────────────────────────────────────
if __name__ == "__main__":
    data = collect_all()
    write_outputs(data)
    print("\n🎉 完成！")
