"""Import cleaned JSONL data into MySQL edu_flow_ai database.

Loads: teachers, courses, class_groups, classrooms, teaching_tasks,
and teaching_task_class_group links.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.db.config import connect, load_db_config

DATA_DIR = PROJECT_ROOT / "data" / "real-dataset"


def import_all() -> None:
    cfg = load_db_config()
    conn = connect(cfg)
    cursor = conn.cursor()

    try:
        # ── 1. Teachers ──────────────────────────────────────────
        print("[1/6] Importing teachers...")
        teachers = _read_jsonl(DATA_DIR / "teachers.jsonl")
        teacher_ids: dict[str, int] = {}
        for i, t in enumerate(teachers, start=1):
            name = (t.get("name") or "").strip()
            deps = t.get("departments") or []
            dept = deps[0] if deps else ""
            employee_no = f"T{i:04d}"
            cursor.execute(
                """INSERT INTO teacher (employee_no, password, role, name, department, title, status)
                   VALUES (%s, %s, 'TEACHER', %s, %s, NULL, 'ACTIVE')
                   ON DUPLICATE KEY UPDATE name=VALUES(name), department=VALUES(department)""",
                (employee_no, "123456", name, dept),
            )
            cursor.execute("SELECT id FROM teacher WHERE name = %s", (name,))
            row = cursor.fetchone()
            # On duplicate the lastrowid may be 0; re-fetch
            teacher_ids[name] = row["id"] if row else cursor.lastrowid or i
        conn.commit()
        print(f"  {len(teachers)} teachers imported")

        # ── 2. Courses ───────────────────────────────────────────
        print("[2/6] Importing courses...")
        courses = _read_jsonl(DATA_DIR / "courses_clean.jsonl")
        course_ids: dict[str, int] = {}
        for c in courses:
            code = (c.get("code") or "").strip()
            name = (c.get("name") or "").strip()
            ct = c.get("course_type") or ""
            rrt = c.get("required_room_type") or None
            credits = c.get("credits")
            hours = int(float(c.get("hours") or 0))
            cursor.execute(
                """INSERT INTO course (name, code, credits, course_type, required_room_type, required_hours)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE name=VALUES(name), course_type=VALUES(course_type),
                   required_room_type=VALUES(required_room_type), required_hours=VALUES(required_hours)""",
                (name, code, credits, ct, rrt, hours),
            )
            cursor.execute("SELECT id FROM course WHERE code = %s", (code,))
            row = cursor.fetchone()
            course_ids[code] = row["id"] if row else cursor.lastrowid
        conn.commit()
        print(f"  {len(courses)} courses imported")

        # ── 3. Class Groups ─────────────────────────────────────
        print("[3/6] Importing class_groups...")
        cgs = _read_jsonl(DATA_DIR / "class_groups.jsonl")
        cg_ids: dict[str, int] = {}
        for cg in cgs:
            name = (cg.get("name") or "").strip()
            major = (cg.get("major") or "").strip()
            dept = (cg.get("department") or "").strip()
            grade = (cg.get("grade") or "").strip()
            sc = cg.get("student_count")
            cursor.execute(
                """INSERT INTO class_group (name, major, department, grade, student_count)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE major=VALUES(major), department=VALUES(department),
                   grade=VALUES(grade), student_count=VALUES(student_count)""",
                (name, major, dept, grade, sc),
            )
            cursor.execute("SELECT id FROM class_group WHERE name = %s", (name,))
            row = cursor.fetchone()
            cg_ids[name] = row["id"] if row else cursor.lastrowid
        conn.commit()
        print(f"  {len(cgs)} class_groups imported")

        # ── 4. Classrooms ───────────────────────────────────────
        print("[4/6] Importing classrooms...")
        rooms = _read_jsonl(DATA_DIR / "classrooms_clean.jsonl")
        room_ids: dict[str, int] = {}
        for r in rooms:
            name = (r.get("name") or "").strip()
            rtype = r.get("classroom_type") or None
            cap = r.get("capacity") or 0
            cursor.execute(
                """INSERT INTO classroom (name, capacity, classroom_type)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE capacity=VALUES(capacity), classroom_type=VALUES(classroom_type)""",
                (name, cap, rtype),
            )
            cursor.execute("SELECT id FROM classroom WHERE name = %s", (name,))
            row = cursor.fetchone()
            room_ids[name] = row["id"] if row else cursor.lastrowid
        conn.commit()
        print(f"  {len(rooms)} classrooms imported")

        # ── 5. Time Slots ───────────────────────────────────────
        print("[5/6] Importing time_slots...")
        time_slot_count = import_time_slots(cursor)
        conn.commit()
        print(f"  {time_slot_count} time_slots imported")

        # ── 6. Teaching Tasks + Class Group Links ───────────────
        print("[6/6] Importing teaching_tasks + links...")
        tasks = _read_jsonl(DATA_DIR / "teaching_tasks_clean.jsonl")
        inserted = 0
        reused = 0
        skipped = 0
        for t in tasks:
            course_code = (t.get("course_code") or "").strip()
            teacher_name = (t.get("teacher") or "").strip()
            class_name = (t.get("class_group") or "").strip()
            total_hours = int(float(t.get("total_hours") or 0))

            course_id = course_ids.get(course_code)
            tid = teacher_ids.get(teacher_name)
            cgid = cg_ids.get(class_name)

            if not course_id:
                print(f"  WARN: course '{course_code}' not found — skip")
                skipped += 1
                continue
            if not tid:
                print(f"  WARN: teacher '{teacher_name}' not found — skip")
                skipped += 1
                continue
            if not cgid:
                print(f"  WARN: class_group '{class_name}' not found — skip")
                skipped += 1
                continue

            # Get required_room_type from course
            cursor.execute(
                "SELECT required_room_type FROM course WHERE id = %s", (course_id,)
            )
            cr = cursor.fetchone()
            required_room = cr["required_room_type"] if cr else None

            cursor.execute(
                """SELECT tt.id
                   FROM teaching_task tt
                   JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
                   WHERE tt.course_id = %s
                     AND tt.primary_teacher_id = %s
                     AND ttcg.class_group_id = %s
                     AND COALESCE(tt.required_room_type, '') = COALESCE(%s, '')
                   LIMIT 1""",
                (course_id, tid, cgid, required_room),
            )
            existing = cursor.fetchone()
            if existing:
                task_id = existing["id"]
                reused += 1
            else:
                cursor.execute(
                    """INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, required_room_type)
                       VALUES (%s, %s, %s, %s)""",
                    (course_id, tid, total_hours, required_room),
                )
                task_id = cursor.lastrowid
                inserted += 1

            cursor.execute(
                """INSERT INTO teaching_task_class_group (teaching_task_id, class_group_id)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE teaching_task_id=teaching_task_id""",
                (task_id, cgid),
            )

        conn.commit()
        print(f"  {inserted} tasks inserted, {reused} reused, {skipped} skipped")

    finally:
        cursor.close()
        conn.close()

    print("\nImport complete!")


def import_time_slots(cursor, *, weeks: int = 20, weekdays: int = 7, periods: int = 5) -> int:
    labels = {
        1: "1-2节",
        2: "3-4节",
        3: "5-6节",
        4: "7-8节",
        5: "9-11节",
    }
    inserted = 0
    for week in range(1, weeks + 1):
        for day in range(1, weekdays + 1):
            for period in range(1, periods + 1):
                label = f"第{week}周 周{day} {labels.get(period, f'第{period}节')}"
                cursor.execute(
                    """INSERT IGNORE INTO time_slot (week_number, day_of_week, period_index, label)
                       VALUES (%s, %s, %s, %s)""",
                    (week, day, period, label),
                )
                inserted += int(cursor.rowcount or 0)
    return inserted


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    import_all()
