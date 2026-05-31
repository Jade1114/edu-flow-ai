#!/usr/bin/env python3
"""
把解析好的真实课表数据灌进 MySQL。

用法：
    python3 scripts/import_to_db.py [--truncate]

流程：
    1. teacher      ← teachers.json
    2. course       ← courses.json  
    3. classroom    ← classrooms.json
    4. class_group  ← class_groups.json
    5. time_slot    ← 自动生成 1-20周 × 1-5天 × 1-5节次
    6. teaching_task ← teaching_tasks.json（关联 course_id / teacher_id / classroom_id）
"""

import json
import pymysql
import os
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "real-dataset"
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "20041114Liuyu!",
    "database": "edu_flow_ai",
    "charset": "utf8mb4",
}

TRUNCATE = "--truncate" in sys.argv


def db():
    return pymysql.connect(**DB_CONFIG)


def load_json(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def truncate_tables(cursor):
    tables = [
        "course_assignment", "allocation_item_adjustment_log", "allocation_item",
        "allocation_scheme_feedback", "allocation_scheme", "allocation_task_teaching_task",
        "allocation_task_generation_config", "allocation_task",
        "teaching_task_class_group", "teaching_task_classroom", "teaching_task",
        "class_group", "classroom", "course", "teacher", "time_slot", "teacher_profile",
        "ml_feedback_event", "model_training_log", "conflict_check_result",
    ]
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in tables:
        cursor.execute(f"DELETE FROM {t}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("  🗑️  已清空所有数据表")


def import_teachers(cursor):
    teachers = load_json("teachers.json")
    count = 0
    for t in teachers:
        name = t["name"][:50]
        dept = t.get("departments", [""])[0] if t.get("departments") else ""
        sql = """INSERT IGNORE INTO teacher (employee_no, password, role, name, department, title, status)
                 VALUES (%s, '123456', 'TEACHER', %s, %s, '未知', 'ACTIVE')"""
        # Generate a pseudo employee_no from name
        emp_no = f"IMP_{name[:20]}"
        cursor.execute(sql, (emp_no, name, dept[:100]))
        if cursor.rowcount > 0:
            count += 1
    print(f"  ✅ teacher: {count} 条")
    return _build_name_id_map(cursor, "teacher", "name")


def import_courses(cursor):
    courses = load_json("courses.json")
    count = 0
    for c in courses:
        sql = """INSERT IGNORE INTO course (name, required_hours, description, status)
                 VALUES (%s, %s, %s, 'ACTIVE')"""
        desc = f"代码:{c['code']} 学分:{c['credits']}"
        cursor.execute(sql, (c["name"][:100], int(c["hours"]), desc[:500]))
        if cursor.rowcount > 0:
            count += 1
    print(f"  ✅ course: {count} 条")
    # Build name→id map, handling case where multiple courses have same name
    name_id = {}
    cursor.execute("SELECT id, name FROM course WHERE status='ACTIVE'")
    for row in cursor.fetchall():
        name_id[row[1]] = row[0]
    return name_id


def import_classrooms(cursor):
    classrooms = load_json("classrooms.json")
    count = 0
    for r in classrooms:
        name = r["name"]
        sql = """INSERT IGNORE INTO classroom (name, capacity, status)
                 VALUES (%s, 40, 'ACTIVE')"""  # default capacity 40
        cursor.execute(sql, (name,))
        if cursor.rowcount > 0:
            count += 1
    print(f"  ✅ classroom: {count} 条")
    return _build_name_id_map(cursor, "classroom", "name")


def import_class_groups(cursor):
    groups = load_json("class_groups.json")
    count = 0
    for g in groups:
        name = g["key"][:100]
        major = g.get("major", "")[:100]
        grade = str(g.get("grade", ""))
        students = g.get("student_count", 0)
        sql = """INSERT IGNORE INTO class_group (name, major, grade, student_count, description)
                 VALUES (%s, %s, %s, %s, '从真实课表导入')"""
        cursor.execute(sql, (name, major, grade, students))
        if cursor.rowcount > 0:
            count += 1
    print(f"  ✅ class_group: {count} 条")
    return _build_name_id_map(cursor, "class_group", "name")


def import_time_slots(cursor):
    """生成标准 20周 × 5天 × 5节次 的时间片"""
    count = 0
    period_labels = {1: "第1-2节", 2: "第3-4节", 3: "第5-6节", 4: "第7-8节", 5: "第9-11节"}
    for week in range(1, 21):
        for day in range(1, 6):  # Mon-Fri
            for period in range(1, 6):
                label = f"第{week}周 周{day} {period_labels[period]}"
                sql = """INSERT IGNORE INTO time_slot (week_number, day_of_week, period_index, label)
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (week, day, period, label))
                if cursor.rowcount > 0:
                    count += 1
    print(f"  ✅ time_slot: {count} 条（{20}周 × {5}天 × {5}节次）")


def import_teaching_tasks(cursor, course_map, teacher_map, classroom_map):
    tasks = load_json("teaching_tasks.json")
    count = 0
    skipped = 0
    for tt in tasks:
        course_id = course_map.get(tt["course_name"])
        teacher_id = teacher_map.get(tt["teacher"])
        if not course_id or not teacher_id:
            skipped += 1
            continue
        sql = """INSERT IGNORE INTO teaching_task
                 (course_id, primary_teacher_id, total_hours, notes, status)
                 VALUES (%s, %s, %s, %s, 'ACTIVE')"""
        notes = f"班级:{tt['class_group']} 学期:{tt['semester']} 教室:{','.join(tt['rooms'][:3])}"
        cursor.execute(sql, (course_id, teacher_id, int(tt["total_hours"]), notes[:500]))
        if cursor.rowcount > 0:
            count += 1
    print(f"  ✅ teaching_task: {count} 条（跳过 {skipped} 条无映射）")


def _build_name_id_map(cursor, table, name_col):
    cursor.execute(f"SELECT id, {name_col} FROM {table}")
    return {row[1]: row[0] for row in cursor.fetchall()}


def main():
    print("=" * 50)
    print("📦 真实课表数据导入工具")
    print("=" * 50)

    conn = db()
    try:
        with conn.cursor() as cursor:
            if TRUNCATE:
                truncate_tables(cursor)

            print("\n📥 1/6 导入教师...")
            teacher_map = import_teachers(cursor)

            print("\n📥 2/6 导入课程...")
            course_map = import_courses(cursor)

            print("\n📥 3/6 导入教室...")
            classroom_map = import_classrooms(cursor)

            print("\n📥 4/6 导入班级...")
            class_group_map = import_class_groups(cursor)

            print("\n📥 5/6 生成时间片...")
            import_time_slots(cursor)

            print("\n📥 6/6 导入教学任务...")
            import_teaching_tasks(cursor, course_map, teacher_map, classroom_map)

            conn.commit()
            print(f"\n{'='*50}")
            print("🎉 导入完成！")

            # 统计
            cursor.execute("SELECT COUNT(*) FROM teacher")
            print(f"   teacher: {cursor.fetchone()[0]}")
            cursor.execute("SELECT COUNT(*) FROM course")
            print(f"   course: {cursor.fetchone()[0]}")
            cursor.execute("SELECT COUNT(*) FROM classroom")
            print(f"   classroom: {cursor.fetchone()[0]}")
            cursor.execute("SELECT COUNT(*) FROM class_group")
            print(f"   class_group: {cursor.fetchone()[0]}")
            cursor.execute("SELECT COUNT(*) FROM time_slot")
            print(f"   time_slot: {cursor.fetchone()[0]}")
            cursor.execute("SELECT COUNT(*) FROM teaching_task")
            print(f"   teaching_task: {cursor.fetchone()[0]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
