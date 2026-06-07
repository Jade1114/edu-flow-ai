#!/usr/bin/env python3
"""
根据教师课表解析出的 JSONL，补充教室分类和课程/任务类型。
产出：
  1. classrooms.jsonl      — 教室名称 + 类型
  2. courses.jsonl (更新)   — 增加 course_type + required_room_type
  3. teaching_tasks.jsonl (更新) — 增加 required_room_type
"""

import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "parsed"

# ─── 教室分类 ────────────────────────────────────────

def is_ji_fang(room_name: str) -> bool:
    """机房判断：教室名以数字 9 开头"""
    return room_name.strip().startswith('9')


def classify_rooms(tasks_path: Path) -> dict:
    """从教学任务中提取所有教室并分类"""
    rooms = {}
    with open(tasks_path) as f:
        for line in f:
            t = json.loads(line)
            for r in t.get('rooms', []):
                r = r.strip()
                if r and r not in rooms:
                    room_type = '机房' if is_ji_fang(r) else '普通教室'
                    rooms[r] = room_type
    return rooms


# ─── 课程/任务分类 ────────────────────────────────────

def classify_courses_and_tasks(tasks_path: Path, rooms: dict):
    """为每个课程和教学任务推断上机/理论课类型"""
    # 先过一遍：列出每个课程用了哪些房间类型
    course_has_ji_fang = defaultdict(bool)
    tasks = []
    with open(tasks_path) as f:
        for line in f:
            t = json.loads(line)
            tasks.append(t)
            code = t['course_code']
            for r in t.get('rooms', []):
                rtype = rooms.get(r.strip(), '普通教室')
                if rtype == '机房':
                    course_has_ji_fang[code] = True

    # 更新教学任务
    updated_tasks = []
    for t in tasks:
        code = t['course_code']
        # 该任务如果有机房房间 → 上机课
        task_has_ji_fang = any(
            rooms.get(r.strip(), '普通教室') == '机房'
            for r in t.get('rooms', [])
        )
        t['required_room_type'] = '机房' if task_has_ji_fang else '普通教室'
        updated_tasks.append(t)

    # 课程类型：只要有用机房的 → 上机课
    course_types = {}
    for code, has_jf in course_has_ji_fang.items():
        course_types[code] = {
            'course_type': '上机课' if has_jf else '理论课',
            'required_room_type': '机房' if has_jf else '普通教室',
        }

    return course_types, updated_tasks


# ─── 输出 ────────────────────────────────────────────

def write_jsonl(path: Path, rows: list[dict]):
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


# ─── 主入口 ──────────────────────────────────────────

def main():
    tasks_path = DATA_DIR / "teaching_tasks.jsonl"
    courses_path = DATA_DIR / "courses.jsonl"

    if not tasks_path.exists():
        print(f"[错误] 找不到 {tasks_path}", file=__import__('sys').stderr)
        return

    # 1. 教室分类
    rooms = classify_rooms(tasks_path)
    classrooms_list = [{'name': name, 'classroom_type': rtype}
                       for name, rtype in sorted(rooms.items())]
    write_jsonl(DATA_DIR / "classrooms.jsonl", classrooms_list)
    print(f"classrooms.jsonl: {len(classrooms_list)} 条")
    ji_fang_count = sum(1 for c in classrooms_list if c['classroom_type'] == '机房')
    normal_count = sum(1 for c in classrooms_list if c['classroom_type'] == '普通教室')
    print(f"  机房 {ji_fang_count}, 普通教室 {normal_count}")

    # 2. 课程分类
    course_types, updated_tasks = classify_courses_and_tasks(tasks_path, rooms)

    # 读取已有课程
    courses = {}
    with open(courses_path) as f:
        for line in f:
            c = json.loads(line)
            code = c['code']
            ct = course_types.get(code, {})
            c['course_type'] = ct.get('course_type', '理论课')
            c['required_room_type'] = ct.get('required_room_type', '普通教室')
            courses[code] = c

    courses_list = list(courses.values())
    write_jsonl(courses_path, courses_list)
    print(f"courses.jsonl: {len(courses_list)} 条")
    shangjic = sum(1 for c in courses_list if c['course_type'] == '上机课')
    lilunc = sum(1 for c in courses_list if c['course_type'] == '理论课')
    print(f"  上机课 {shangjic}, 理论课 {lilunc}")

    # 3. 写回教学任务
    write_jsonl(tasks_path, updated_tasks)
    print(f"teaching_tasks.jsonl: {len(updated_tasks)} 条（已更新 required_room_type）")

    print()
    print("全部更新完成 ✅")


if __name__ == '__main__':
    main()
