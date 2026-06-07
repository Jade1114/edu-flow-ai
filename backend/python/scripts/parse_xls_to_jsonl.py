#!/usr/bin/env python3
"""
解析 schema01/ 下所有班级课表 .xls 文件，输出 4 个 JSONL：
  1. teachers.jsonl       — 教师
  2. class_groups.jsonl   — 班级
  3. courses.jsonl        — 课程
  4. teaching_tasks.jsonl — 教学任务

用法：
  cd backend && python3 python/scripts/parse_xls_to_jsonl.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import xlrd

# ─── 路径 ───────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "schema01"
OUT_DIR  = Path(__file__).resolve().parents[2] / "data" / "parsed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── 辅助函数 ────────────────────────────────────────

def parse_title(row0: str) -> dict:
    """从标题行提取 院系、专业、班级、人数"""
    info = {}
    # "2025-2026学年第1学期电子信息与计算机工程系(学院)软件工程(专业)2022级软件工程1班(班级)课表共52人"
    # 提取院系：取第一个 (学院) 前的完整名称
    m = re.search(r'第\d+学期(.+?)\(学院\)', row0)
    if m:
        info['department'] = m.group(1).strip() + '(学院)'
    else:
        m = re.search(r'(.+?)\(学院\)', row0)
        if m:
            info['department'] = m.group(1).strip() + '(学院)'
    m = re.search(r'(\d+)人', row0)
    if m:
        info['student_count'] = int(m.group(1))
    # 提取班级全名：如 "2022级软件工程1班"
    m = re.search(r'(\d{4}级.+?\d+班)', row0)
    if m:
        info['class_name'] = m.group(1)
    # 提取专业名
    m = re.search(r'\(专业\)', row0)
    if m:
        # 取 (专业) 前面最近的位置
        before = row0[:m.start()]
        majors = re.findall(r'([^()]+)', before)
        if majors:
            info['major'] = majors[-1].strip()
    return info


def _clean_course_name(name: str) -> str:
    """清洗课程名，去掉【专】N人 等前缀"""
    name = re.sub(r'【专】\s*\d+\s*人\s*', '', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name


def parse_course_detail_line(text: str) -> list[dict]:
    """解析 Row24 的课程详细信息行，返回 [{code, name, teachers, rooms, hours}]"""
    courses = []
    # 匹配模式：课程名(代码)(ID[...]学分[...]) 时[...] 师[...] 室[...]
    # 先按 室[...] 分割（因为每个课程块都以 室[...] 结尾或含空格分割）
    pattern = r'(.+?)\(([^)]+)\)\(ID\[\d+\]学分\[([^\]]*)\]\)\s*时\[([^\]]*)\]\s*师\[([^\]]*)\]\s*室\[([^\]]*)\]'
    for m in re.finditer(pattern, text):
        course_name = m.group(1).strip()
        course_code = m.group(2).strip()
        hours_str = m.group(4).strip()
        teachers_str = m.group(5).strip()
        rooms_str = m.group(6).strip()

        courses.append({
            'code': course_code,
            'name': _clean_course_name(course_name),
            'teachers': [t.strip() for t in teachers_str.split(',') if t.strip()],
            'rooms': [r.strip() for r in rooms_str.split(',') if r.strip()],
            'total_hours': float(hours_str) if hours_str else 0,
        })
    return courses


def parse_schedule_cell(cell_value):
    """解析课表格子，返回 (course_code, room_name) 或 None"""
    if not cell_value or not isinstance(cell_value, str):
        return None
    cell = cell_value.strip()
    if not cell:
        return None
    # 跳过非课程内容
    skip_words = {'报到注册', '国庆节', '中秋节', '元旦节', '期末考试',
                  '全国计算机等级考试', '大学英语四、六级考试', '入学教育',
                  '军训', '毕业教育', '实践周', '运动会', ''}
    if cell in skip_words:
        return None
    if '报到' in cell or '注册' in cell or '节' in cell or '考试' in cell:
        return None

    # 格式：课程代码\n教室名 或 课程代码\n教室名\n教室名
    parts = cell.split('\n')
    code = parts[0].strip()
    if not code:
        return None
    # 去掉代码中的节次后缀，如 "形033(9-10)" → "形033"
    code_clean = re.sub(r'\(\d+[-\d,]*\)', '', code).strip()
    if not code_clean:
        return None
    # 教室可能在后面多行（有时多个教室换行列出）
    # 取第一个非空且不含特殊标记的作为教室
    room = ''
    for p in parts[1:]:
        p = p.strip()
        if p and not any(kw in p for kw in skip_words):
            room = p
            break
    return (code_clean, room)


# ─── 主解析函数 ─────────────────────────────────────

def parse_all_xls(data_dir: Path) -> dict:
    """解析所有 .xls 文件，返回聚合后的数据"""
    xls_files = sorted(data_dir.glob("*.xls"))
    if not xls_files:
        # 也试试 .xlsx
        xls_files = sorted(data_dir.glob("*.xlsx"))
    if not xls_files:
        print(f"[错误] 在 {data_dir} 下未找到 .xls 文件", file=sys.stderr)
        sys.exit(1)

    print(f"找到 {len(xls_files)} 个课表文件")

    # 聚合数据
    teachers_set = {}       # name -> {name, departments?}
    class_groups = {}       # class_name -> {name, major, department, grade, student_count}
    courses = {}            # code -> {code, name}
    teaching_tasks = []     # [{course_code, teacher_name, class_group_name, total_hours, rooms}]

    file_errors = 0

    for fpath in xls_files:
        try:
            wb = xlrd.open_workbook(str(fpath))
            sheet = wb.sheet_by_index(0)
        except Exception as e:
            print(f"  [跳过] 无法读取 {fpath.name}: {e}", file=sys.stderr)
            file_errors += 1
            continue

        if sheet.nrows < 25:
            print(f"  [跳过] {fpath.name} 行数不足 ({sheet.nrows})", file=sys.stderr)
            file_errors += 1
            continue

        # ── 第 1 步：解析标题 ──
        title = str(sheet.cell_value(0, 0) or '')
        cls_info = parse_title(title)
        class_name = cls_info.get('class_name', '')
        if not class_name:
            print(f"  [跳过] {fpath.name}: 无法解析班级名", file=sys.stderr)
            file_errors += 1
            continue

        department = cls_info.get('department', '电子信息与计算机工程系(学院)')
        major = cls_info.get('major', '')
        student_count = cls_info.get('student_count', 0)
        grade = class_name[:4] if len(class_name) >= 4 else ''

        # ── 第 2 步：解析 Row 24 课程详情（含教师信息） ──
        detail_text = ''
        if sheet.nrows > 24:
            detail_text = str(sheet.cell_value(24, 0) or '')
        detail_courses = parse_course_detail_line(detail_text)

        # detail_courses 中 code -> {name, teachers, rooms, hours} 的映射
        detail_map = {c['code']: c for c in detail_courses}

        # 收集该班级所有出现的课程代码（从课表格子中）
        class_course_codes = set()
        class_rooms_for_course = defaultdict(set)
        # 从 Row 4 到 Row 23（第 1-20 周）
        for r in range(4, min(sheet.nrows - 1, 24)):
            week_val = str(sheet.cell_value(r, 0) or '').strip()
            # Col 0 = 周次, Col 1 = 日期, Col 2-36 = 课表
            for c in range(2, sheet.ncols):
                cell_val = str(sheet.cell_value(r, c) or '').strip()
                parsed = parse_schedule_cell(cell_val)
                if parsed:
                    code, room = parsed
                    class_course_codes.add(code)
                    if room:
                        class_rooms_for_course[code].add(room)

        # ── 第 3 步：注册班级 ──
        if class_name and class_name not in class_groups:
            class_groups[class_name] = {
                'name': class_name,
                'major': major,
                'department': department,
                'grade': grade,
                'student_count': student_count,
            }

        # ── 第 4 步：注册课程和教师 ──
        for code in class_course_codes:
            detail = detail_map.get(code, {})
            course_name = detail.get('name', code)  # 没有详细名就用代码

            # 注册课程
            if code not in courses:
                courses[code] = {
                    'code': code,
                    'name': course_name,
                }

            # 注册教师
            teachers_list = detail.get('teachers', [])
            for tname in teachers_list:
                if tname and tname not in teachers_set:
                    teachers_set[tname] = {'name': tname}

            # ── 第 5 步：生成教学任务 ──
            # 一个 课程+班级 为一个教学任务
            rooms = list(class_rooms_for_course.get(code, []))
            # 如果 detail 有 rooms 信息，合并
            detail_rooms = detail.get('rooms', [])
            all_rooms = list(set(rooms + detail_rooms))

            # 过滤掉虚拟教室
            all_rooms = [r for r in all_rooms if '虚拟' not in r]

            total_hours = detail.get('total_hours', 0)

            if teachers_list:
                for tname in teachers_list:
                    teaching_tasks.append({
                        'course_code': code,
                        'teacher_name': tname,
                        'class_group_name': class_name,
                        'total_hours': total_hours,
                        'rooms': all_rooms,
                    })
            else:
                # 没有找到教师，但仍然记录任务（教师名为空，稍后处理）
                teaching_tasks.append({
                    'course_code': code,
                    'teacher_name': '',
                    'class_group_name': class_name,
                    'total_hours': total_hours,
                    'rooms': all_rooms,
                })

    print(f"解析完成: {file_errors} 个文件出错")
    return {
        'teachers': teachers_set,
        'class_groups': class_groups,
        'courses': courses,
        'teaching_tasks': teaching_tasks,
    }


# ─── 输出 JSONL ─────────────────────────────────────

def write_jsonl(path: Path, rows: list[dict]):
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"  {path.name}: {len(rows)} 条")


# ─── 去重教学任务 ────────────────────────────────────

def dedup_teaching_tasks(tasks: list[dict]) -> list[dict]:
    """同一 课程+班级+教师 只保留一条，合并 rooms"""
    seen = {}
    for t in tasks:
        key = (t['course_code'], t['class_group_name'], t['teacher_name'])
        if key in seen:
            existing = seen[key]
            existing['rooms'] = list(set(existing['rooms'] + t['rooms']))
            if not existing['total_hours'] and t['total_hours']:
                existing['total_hours'] = t['total_hours']
        else:
            seen[key] = dict(t)
    return list(seen.values())


# ─── 主入口 ──────────────────────────────────────────

def main():
    print("=" * 50)
    print("解析课表 Excel 文件 → JSONL")
    print("=" * 50)
    print()

    data = parse_all_xls(DATA_DIR)

    # 输出 JSONL
    # 1. 教师
    teachers_list = list(data['teachers'].values())
    write_jsonl(OUT_DIR / 'teachers.jsonl', teachers_list)

    # 2. 班级
    class_groups_list = list(data['class_groups'].values())
    write_jsonl(OUT_DIR / 'class_groups.jsonl', class_groups_list)

    # 3. 课程
    courses_list = list(data['courses'].values())
    write_jsonl(OUT_DIR / 'courses.jsonl', courses_list)

    # 4. 教学任务（去重）
    tasks_deduped = dedup_teaching_tasks(data['teaching_tasks'])
    write_jsonl(OUT_DIR / 'teaching_tasks.jsonl', tasks_deduped)

    print()
    print("=" * 50)
    print("汇总")
    print("=" * 50)
    print(f"  教师:     {len(teachers_list)} 人")
    print(f"  班级:     {len(class_groups_list)} 个")
    print(f"  课程:     {len(courses_list)} 门")
    print(f"  教学任务: {len(tasks_deduped)} 条")
    print()
    print(f"输出目录: {OUT_DIR}/")


if __name__ == '__main__':
    main()
