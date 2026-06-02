#!/usr/bin/env python3
"""
真实课表数据 → MySQL 导入脚本（v3 清理版）
用法：
    python3 scripts/import_to_db.py [--truncate]

流程：
    1. teacher        ← teachers.jsonl
    2. course         ← courses.jsonl
    3. classroom      ← classrooms.jsonl（含类型/楼栋推断）
    4. class_group    ← class_groups.jsonl
    5. time_slot      ← 自动生成 1-20周 × 1-5天 × 1-5节次
    6. teaching_task  ← teaching_tasks.jsonl（去重 + 关联）
    7. 推断 course_type / classroom_type

数据清洗要点：
    - 教学任务按 (课程, 教师, 班级) 三元组去重
    - 课程学时取首次出现值而非 max（防止跨班级膨胀）
    - 教室类型/楼栋从房间号规则推断
    - 课程类型从实际使用的教室类型推断
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
SKIP_TASKS = "--skip-tasks" in sys.argv


def log(msg): print(f"  {msg}")


def db():
    return pymysql.connect(**DB)


def load_jsonl(name):
    path = DATA_DIR / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").strip().split("\n") if line.strip()]


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
        dept = (t.get("departments") or [""])[0] if isinstance(t.get("departments"), list) else (t.get("departments") or "")
        sql = """INSERT IGNORE INTO teacher
                 (employee_no, password, role, name, department, title, status)
                 VALUES (%s, '123456', 'TEACHER', %s, %s, '未知', 'ACTIVE')"""
        cursor.execute(sql, (emp_no, name, str(dept)[:100]))
        if cursor.rowcount > 0:
            count += 1
    cursor.execute("OPTIMIZE TABLE teacher")
    log(f"✅ teacher: {count}/{len(data)} 条")
    return _name_id_map(cursor, "teacher")


def import_courses(cursor):
    data = load_jsonl("courses.jsonl")
    count = 0
    for c in data:
        hours = int(c.get("hours", 32))
        desc = f"从真实课表导入 | 代码:{c['code']}"
        course_type = c.get("course_type") or None
        room_type = c.get("required_room_type") or None
        sql = """INSERT IGNORE INTO course
                 (name, code, credits, course_type, required_room_type, required_hours, description, status)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE')"""
        cursor.execute(sql, (
            c["name"][:100],
            c["code"][:32],
            c.get("credits", 0),
            course_type,
            room_type,
            hours,
            desc[:500],
        ))
        if cursor.rowcount > 0:
            count += 1
    log(f"✅ course: {count}/{len(data)} 条")
    return _code_id_map(cursor, "course")


def import_classrooms(cursor):
    data = load_jsonl("classrooms.jsonl")
    count = 0
    for r in data:
        name = r["name"].strip()
        ctype = r.get("classroom_type") or None
        cap = int(r.get("capacity", 80))
        sql = """INSERT IGNORE INTO classroom (name, capacity, classroom_type, status)
                 VALUES (%s, %s, %s, 'ACTIVE')"""
        cursor.execute(sql, (name, cap, ctype))
        if cursor.rowcount > 0:
            count += 1
    log(f"✅ classroom: {count}/{len(data)} 间")
    return _name_id_map(cursor, "classroom")


def import_class_groups(cursor):
    data = load_jsonl("class_groups.jsonl")
    count = 0
    for g in data:
        sql = """INSERT IGNORE INTO class_group
                 (name, major, department, grade, student_count)
                 VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(sql, (
            g["name"][:100],
            (g.get("major") or "")[:100],
            (g.get("department") or "")[:100],
            str(g.get("grade", "")),
            int(g.get("student_count", 0)),
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


def import_teaching_tasks(cursor, course_id_by_code, teacher_id_map, class_group_map):
    data = load_jsonl("teaching_tasks.jsonl")

    task_count = 0
    cg_count = 0
    skipped = 0
    seen = set()  # 去重：(course_id, class_group_id)

    for tt in data:
        course_id = course_id_by_code.get(tt["course_code"])
        teacher_id = teacher_id_map.get(tt["teacher"])

        if not course_id or not teacher_id:
            skipped += 1
            continue

        cg_id = class_group_map.get(tt["class_group"])

        # 同一课程+同一班级只保留一条（协教已由 parse 去重）
        dedup_key = (course_id, cg_id)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        note = f"{tt['class_group']} / {tt['teacher']}"

        sql = """INSERT INTO teaching_task
                 (course_id, primary_teacher_id, total_hours, notes, status)
                 VALUES (%s, %s, %s, %s, 'ACTIVE')"""
        cursor.execute(sql, (course_id, teacher_id, int(tt["total_hours"]), note[:500]))
        task_id = cursor.lastrowid
        task_count += 1

        # 关联班级
        if cg_id:
            cursor.execute(
                "INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id) VALUES (%s, %s)",
                (task_id, cg_id),
            )
            cg_count += cursor.rowcount

    log(f"✅ teaching_task: {task_count} 条（跳过 {skipped} 条无映射）")
    log(f"✅ teaching_task_class_group: {cg_count} 条关联")


def infer_course_types(cursor):
    """兜底：parse 阶段未推断到的课程类型 + 同步 teaching_task"""
    log("🧠 补漏课程类型 + 同步 teaching_task...")

    # 按名称关键词补漏（仅限还是 NULL 的）
    cursor.execute("""
        UPDATE course SET course_type = '上机课', required_room_type = '机房'
        WHERE course_type IS NULL AND (name LIKE '%上机%' OR name LIKE '%实验%' OR name LIKE '%实训%')
    """)
    cursor.execute("""
        UPDATE course SET course_type = '实践课', required_room_type = NULL
        WHERE course_type IS NULL AND (name LIKE '%实习%' OR name LIKE '%实践%' OR name LIKE '%军事%'
               OR name LIKE '%校企%' OR name LIKE '%工程素质%')
    """)
    cursor.execute("""
        UPDATE course SET course_type = '理论课', required_room_type = '普通教室'
        WHERE course_type IS NULL
    """)

    # 同步 teaching_task.required_room_type
    cursor.execute("""
        UPDATE teaching_task tt
        JOIN course c ON c.id = tt.course_id
        SET tt.required_room_type = c.required_room_type
        WHERE tt.required_room_type IS NULL
    """)
    log("✅ 补漏完成")


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
    mode = "基础数据（不含教学任务）" if SKIP_TASKS else "全量数据"
    print(f"📦 真实课表数据导入工具 v3 — {mode}")
    print("=" * 50)

    conn = db()
    try:
        with conn.cursor() as cursor:
            if TRUNCATE:
                truncate_tables(cursor)

            total_steps = 5 if SKIP_TASKS else 7

            print(f"\n📥 1/{total_steps} 教师...")
            teacher_map = import_teachers(cursor)

            print(f"\n📥 2/{total_steps} 课程...")
            course_by_code = import_courses(cursor)

            print(f"\n📥 3/{total_steps} 教室...")
            room_map = import_classrooms(cursor)

            print(f"\n📥 4/{total_steps} 班级...")
            cg_map = import_class_groups(cursor)

            print(f"\n📥 5/{total_steps} 时间片...")
            import_time_slots(cursor)

            if not SKIP_TASKS:
                print(f"\n📥 6/{total_steps} 教学任务 + 班级关联...")
                import_teaching_tasks(cursor, course_by_code, teacher_map, cg_map)

                print(f"\n🧠 7/{total_steps} 推断课程类型...")
                infer_course_types(cursor)

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
