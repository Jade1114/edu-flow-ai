#!/usr/bin/env python3
"""根据基础数据生成 300 条教学任务（仅理论课 + 上机课）。

用法：
    cd edu-flow-ai
    python3 scripts/generate_mock_tasks.py

流程：
    1. 从 DB 读取教师、课程（过滤理论/上机）、班级
    2. 教师-课程按院系匹配
    3. 自动生成教学任务 + 班级关联
"""

import pymysql
import random
import sys
from collections import defaultdict
from pathlib import Path

DB = {
    "host": "localhost", "port": 3306,
    "user": "root", "password": "20041114Liuyu!",
    "database": "edu_flow_ai", "charset": "utf8mb4",
}


def log(msg): print(f"  {msg}")


def db():
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB)


TASK_COUNT = 300

# 每种课程类型的课时分布（参考真实数据）
HOURS_RANGE = {
    "理论课": [32, 40, 48, 64, 80],
    "上机课": [24, 32, 40, 48],
}

# 每个教学任务关联的班级数
CLASS_GROUP_COUNT_RANGE = [1, 1, 1, 1, 2, 2, 3]  # 大多数1个班，少数合班


def main():
    rng = random.Random(42)

    conn = db()
    try:
        with conn.cursor() as cursor:
            # 1. 读取教师
            cursor.execute("SELECT id, name, department FROM teacher WHERE status = 'ACTIVE'")
            teachers = cursor.fetchall()
            teacher_by_dept = defaultdict(list)
            for t in teachers:
                teacher_by_dept[t["department"]].append(t)
            log(f"教师: {len(teachers)} 人")

            # 2. 读取课程（只保留理论课 + 上机课）
            cursor.execute("""
                SELECT id, name, code, course_type, required_room_type, required_hours
                FROM course
                WHERE course_type IN ('理论课', '上机课') AND status = 'ACTIVE'
            """)
            courses = cursor.fetchall()
            log(f"课程（理论+上机）: {len(courses)} 门")
            if len(courses) < TASK_COUNT // 2:
                log("⚠️ 课程数量不够，会重复使用")

            courses_by_type = defaultdict(list)
            for c in courses:
                courses_by_type[c["course_type"]].append(c)

            # 3. 读取班级
            cursor.execute("SELECT id, name, major, department, student_count FROM class_group")
            class_groups = cursor.fetchall()
            log(f"班级: {len(class_groups)} 个")

            # 4. 生成教学任务
            tasks_data = []
            seen_combos = set()

            # 按课程类型比例分配（理论课约70%，上机课30%）
            theory_count = int(TASK_COUNT * 0.7)
            computer_count = TASK_COUNT - theory_count
            type_plan = ["理论课"] * theory_count + ["上机课"] * computer_count
            rng.shuffle(type_plan)

            task_insert_sql = """
                INSERT INTO teaching_task
                    (course_id, primary_teacher_id, total_hours, required_room_type, notes, status)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
            """
            cg_insert_sql = """
                INSERT INTO teaching_task_class_group (teaching_task_id, class_group_id)
                VALUES (%s, %s)
            """

            created = 0
            attempts = 0
            max_attempts = TASK_COUNT * 10

            while created < TASK_COUNT and attempts < max_attempts:
                attempts += 1
                ctype = type_plan[created]

                # 选课程
                pool = courses_by_type.get(ctype, [])
                if not pool:
                    continue
                course = rng.choice(pool)

                # 选教师（优先同院系）
                course_name = course["name"].lower()
                # 尝试找课程所属院系的教师
                dept_candidates = []
                for dept, tlist in teacher_by_dept.items():
                    # 粗略匹配：课程名包含院系关键词
                    if any(kw in course_name for kw in dept.lower().replace("系", "").replace("学院", "").split()):
                        dept_candidates.extend(tlist)
                if not dept_candidates:
                    # 随机选
                    dept_candidates = teachers
                teacher = rng.choice(dept_candidates)

                # 选班级（取 1-3 个）
                cg_count = rng.choice(CLASS_GROUP_COUNT_RANGE)
                selected_cgs = rng.sample(class_groups, min(cg_count, len(class_groups)))

                # 去重：同一课程+同一教师+同一班级不重复
                cg_ids = tuple(sorted(c["id"] for c in selected_cgs))
                combo_key = (course["id"], teacher["id"], cg_ids)
                if combo_key in seen_combos:
                    continue
                seen_combos.add(combo_key)

                # 确定课时
                hours = rng.choice(HOURS_RANGE.get(ctype, [40]))

                # 备注
                cg_names = ",".join(c["name"] for c in selected_cgs)
                notes = f"{cg_names} / {teacher['name']}"

                tasks_data.append({
                    "course": course,
                    "teacher": teacher,
                    "class_groups": selected_cgs,
                    "total_hours": hours,
                    "notes": notes[:500],
                })
                created += 1

            log(f"生成 {created} 条教学任务（尝试 {attempts} 次）")

            # 5. 写入 DB
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("DELETE FROM teaching_task_class_group")
            cursor.execute("DELETE FROM teaching_task")
            cursor.execute("ALTER TABLE teaching_task AUTO_INCREMENT = 1")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            inserted = 0
            for td in tasks_data:
                cursor.execute(task_insert_sql, (
                    td["course"]["id"],
                    td["teacher"]["id"],
                    td["total_hours"],
                    td["course"]["required_room_type"],
                    td["notes"],
                ))
                task_id = cursor.lastrowid

                for cg in td["class_groups"]:
                    cursor.execute(cg_insert_sql, (task_id, cg["id"]))

                inserted += 1
                if inserted % 50 == 0:
                    log(f"  已写入 {inserted}/{created}")

            conn.commit()

            # 6. 统计
            log(f"\n✅ 写入完成: {inserted} 条")
            cursor.execute("""
                SELECT c.course_type, COUNT(*) AS cnt
                FROM teaching_task tt
                JOIN course c ON c.id = tt.course_id
                GROUP BY c.course_type
            """)
            for r in cursor.fetchall():
                log(f"   {r['course_type']}: {r['cnt']}")

            cursor.execute("SELECT COUNT(*) AS cnt FROM teaching_task_class_group")
            log(f"   班级关联: {cursor.fetchone()['cnt']} 条")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 失败：{e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
