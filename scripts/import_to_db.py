#!/usr/bin/env python3
"""
真实课表数据 → MySQL 导入脚本（修正版）
用法：
    python3 scripts/import_to_db.py [--truncate] [--no-code]

流程：
    1. 给 course 表加 code/credits 列
    2. teacher     ← teachers.json
    3. course      ← courses.json
    4. classroom   ← classrooms.json
    5. class_group ← class_groups.json
    6. time_slot   ← 自动生成 1-20周 × 1-5天 × 1-5节次
    7. teaching_task  ← teaching_tasks.json（关联 course/teacher/classroom）
    8. teaching_task_class_group ← 关联教学任务↔班级
"""

import json
import pymysql
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "real-dataset"
DB = {
    "host": "localhost", "port": 3306,
    "user": "root", "password": "20041114Liuyu!",
    "database": "edu_flow_ai", "charset": "utf8mb4",
}
TRUNCATE = "--truncate" in sys.argv
SKIP_CODE = "--no-code" in sys.argv


def log(msg): print(f"  {msg}")


def db():
    return pymysql.connect(**DB)


def load_jsonl(name):
    """读 JSONL 文件，返回 list"""
    path = DATA_DIR / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").strip().split("\n") if line.strip()]


def ensure_course_columns(cursor):
    """给 course 表加 code 和 credits 列（幂等）"""
    cursor.execute("SHOW COLUMNS FROM course LIKE 'code'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE course ADD COLUMN code VARCHAR(32) DEFAULT NULL COMMENT '课程代码' AFTER name")
        cursor.execute("CREATE INDEX idx_course_code ON course(code)")
        log("✅ course 表已添加 code 列")
    cursor.execute("SHOW COLUMNS FROM course LIKE 'credits'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE course ADD COLUMN credits DECIMAL(4,1) DEFAULT NULL COMMENT '学分' AFTER code")
        log("✅ course 表已添加 credits 列")


def truncate_tables(cursor):
    tables = [
        "teaching_task_class_group", "teaching_task_classroom",
        "course_assignment", "allocation_item_adjustment_log", "allocation_item",
        "allocation_scheme_feedback", "allocation_scheme",
        "allocation_task_teaching_task", "allocation_task_generation_config",
        "allocation_task", "teaching_task",
        "class_group", "classroom", "course", "teacher", "time_slot",
        "teacher_profile", "ml_feedback_event", "model_training_log",
    ]
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in tables:
        cursor.execute(f"DELETE FROM {t}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    log("🗑️  已清空所有数据表")


# ── 导入函数 ─────────────────────────────────────────

def import_teachers(cursor):
    data = load_jsonl("teachers.jsonl")
    count = 0
    for t in data:
        name = t["name"][:50]
        emp_no = f"IMP_{name}"[:30]
        dept = t.get("departments", [""])[0] if t.get("departments") else ""
        sql = """INSERT IGNORE INTO teacher
                 (employee_no, password, role, name, department, title, status)
                 VALUES (%s, '123456', 'TEACHER', %s, %s, '未知', 'ACTIVE')"""
        cursor.execute(sql, (emp_no, name, dept[:100]))
        if cursor.rowcount > 0:
            count += 1
    # 重建索引
    cursor.execute("OPTIMIZE TABLE teacher")
    log(f"✅ teacher: {count}/{len(data)} 条")
    return _name_id_map(cursor, "teacher")


def import_courses(cursor):
    data = load_jsonl("courses.jsonl")
    count = 0
    for c in data:
        sql = """INSERT IGNORE INTO course
                 (name, code, credits, required_hours, description, status)
                 VALUES (%s, %s, %s, %s, %s, 'ACTIVE')"""
        desc = f"从真实课表导入 | 代码:{c['code']}"
        cursor.execute(sql, (
            c["name"][:100],
            c["code"][:32],
            c["credits"],
            int(c["hours"]),
            desc[:500],
        ))
        if cursor.rowcount > 0:
            count += 1
    log(f"✅ course: {count}/{len(data)} 条")
    # 返回 name→id 和 code→id 两个映射
    return _name_id_map(cursor, "course"), _code_id_map(cursor, "course")


def import_classrooms(cursor):
    data = load_jsonl("classrooms.jsonl")
    count = 0
    for r in data:
        sql = """INSERT IGNORE INTO classroom (name, capacity, status)
                 VALUES (%s, 40, 'ACTIVE')"""
        cursor.execute(sql, (r["name"],))
        if cursor.rowcount > 0:
            count += 1
    log(f"✅ classroom: {count}/{len(data)} 间")
    return _name_id_map(cursor, "classroom")


def import_class_groups(cursor):
    data = load_jsonl("class_groups.jsonl")
    count = 0
    for g in data:
        sql = """INSERT IGNORE INTO class_group
                 (name, major, grade, student_count, description)
                 VALUES (%s, %s, %s, %s, '从真实课表导入')"""
        cursor.execute(sql, (
            g["key"][:100],
            g.get("major", "")[:100],
            str(g.get("grade", "")),
            g.get("student_count", 0),
        ))
        if cursor.rowcount > 0:
            count += 1
    log(f"✅ class_group: {count}/{len(data)} 个")
    return _name_id_map(cursor, "class_group")


def import_time_slots(cursor):
    """生成 20周 × 5天 × 5节次 = 500 条"""
    labels = {1: "1-2节", 2: "3-4节", 3: "5-6节", 4: "7-8节", 5: "9-11节"}
    count = 0
    for w in range(1, 21):
        for d in range(1, 6):
            for p in range(1, 6):
                lbl = f"第{w}周 周{d} {labels[p]}"
                sql = """INSERT IGNORE INTO time_slot
                         (week_number, day_of_week, period_index, label)
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (w, d, p, lbl))
                if cursor.rowcount > 0:
                    count += 1
    log(f"✅ time_slot: {count} 条（20周×5天×5节次）")


def import_teaching_tasks(cursor, course_id_by_name, teacher_id_map, room_id_map, class_group_map):
    data = load_jsonl("teaching_tasks.jsonl")
    
    # 预处理：class_group_map 的 key 是 "2023级软件工程2班"
    task_count = 0
    cg_count = 0
    skipped = 0
    
    for tt in data:
        course_id = course_id_by_name.get(tt["course_name"])
        teacher_id = teacher_id_map.get(tt["teacher"])
        
        if not course_id or not teacher_id:
            skipped += 1
            continue
        
        # 教室：取第一个可用教室
        first_room = tt.get("rooms", [None])[0]
        room_id = room_id_map.get(first_room) if first_room else None
        
        # 插入 teaching_task
        sql = """INSERT INTO teaching_task
                 (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
                 VALUES (%s, %s, %s, %s, %s, 'ACTIVE')"""
        notes = cls = tt["class_group"]
        cursor.execute(sql, (
            course_id, teacher_id, room_id,
            int(tt["total_hours"]), notes[:500],
        ))
        task_id = cursor.lastrowid
        task_count += 1
        
        # 关联班级 → teaching_task_class_group
        cg_id = class_group_map.get(tt["class_group"])
        if cg_id:
            cursor.execute(
                "INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id) VALUES (%s, %s)",
                (task_id, cg_id),
            )
            cg_count += cursor.rowcount
    
    log(f"✅ teaching_task: {task_count} 条（跳过 {skipped} 条无映射）")
    log(f"✅ teaching_task_class_group: {cg_count} 条关联")


# ── 辅助函数 ─────────────────────────────────────────

def _name_id_map(cursor, table):
    cursor.execute(f"SELECT id, name FROM {table}")
    return {row[1]: row[0] for row in cursor.fetchall()}


def _code_id_map(cursor, table):
    cursor.execute(f"SELECT id, code FROM {table} WHERE code IS NOT NULL")
    return {row[1]: row[0] for row in cursor.fetchall()}


def print_stats(cursor):
    for t in ["teacher", "course", "classroom", "class_group",
              "time_slot", "teaching_task", "teaching_task_class_group"]:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        log(f"   {t}: {cursor.fetchone()[0]}")


# ── 主入口 ───────────────────────────────────────────

def main():
    print("=" * 50)
    print("📦 真实课表数据导入工具 v2")
    print("=" * 50)
    
    conn = db()
    try:
        with conn.cursor() as cursor:
            # 0. 加列
            if not SKIP_CODE:
                ensure_course_columns(cursor)
            
            # 0. 清空
            if TRUNCATE:
                truncate_tables(cursor)
            
            print("\n📥 1/8 教师...")
            teacher_map = import_teachers(cursor)
            
            print("\n📥 2/8 课程...")
            course_by_name, course_by_code = import_courses(cursor)
            
            print("\n📥 3/8 教室...")
            room_map = import_classrooms(cursor)
            
            print("\n📥 4/8 班级...")
            cg_map = import_class_groups(cursor)
            
            print("\n📥 5/8 时间片...")
            import_time_slots(cursor)
            
            print("\n📥 6/8 教学任务 + 班级关联...")
            import_teaching_tasks(cursor, course_by_name, teacher_map, room_map, cg_map)
            
            conn.commit()
            print(f"\n{'='*50}")
            print("🎉 导入完成！")
            print_stats(cursor)
    
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 导入失败：{e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
