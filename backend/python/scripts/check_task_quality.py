#!/usr/bin/env python3
"""
分析教学任务质量：教师负载、课时分布、潜在冲突风险等。
输出一份直观的报告，帮助判断当前排课任务是否合理。
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pymysql

DB = dict(host="localhost", port=3306, user="root",
          password="20041114Liuyu!", database="edu_flow_ai",
          charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)

conn = pymysql.connect(**DB)
cur = conn.cursor()

# ── 1. 基本数据 ──
cur.execute("""
    SELECT tt.id, tt.total_hours, tt.required_room_type,
           c.name AS course_name, c.course_type,
           t.name AS teacher_name, t.id AS teacher_id
    FROM teaching_task tt
    JOIN course c ON c.id = tt.course_id
    JOIN teacher t ON t.id = tt.primary_teacher_id
    WHERE tt.status = 'ACTIVE'
    ORDER BY tt.id
""")
tasks = cur.fetchall()

cur.execute("""
    SELECT tt.id AS task_id, GROUP_CONCAT(DISTINCT cg.name ORDER BY cg.name) AS classes
    FROM teaching_task tt
    JOIN teaching_task_class_group ttcg ON ttcg.teaching_task_id = tt.id
    JOIN class_group cg ON cg.id = ttcg.class_group_id
    GROUP BY tt.id
""")
task_classes = {r["task_id"]: r["classes"] for r in cur.fetchall()}

cur.close()
conn.close()

print("=" * 60)
print("  教学任务质量诊断报告")
print("=" * 60)
print(f"\n总教学任务: {len(tasks)}")

# ── 2. 教师负载分析 ──
print("\n" + "-" * 60)
print("【教师负载】")
print("-" * 60)

teacher_stats = defaultdict(lambda: {"tasks": 0, "hours": 0, "students": set(), "classes": set()})
for t in tasks:
    tid = t["teacher_id"]
    teacher_stats[tid]["name"] = t["teacher_name"]
    teacher_stats[tid]["tasks"] += 1
    teacher_stats[tid]["hours"] += int(t["total_hours"] or 0)
    cls = task_classes.get(t["id"], "")
    for c in cls.split(","):
        if c.strip():
            teacher_stats[tid]["classes"].add(c.strip())

# 按课时降序
ranked = sorted(teacher_stats.items(), key=lambda x: -x[1]["hours"])
print(f"{'教师':<12} {'教学任务':>6} {'总课时':>8} {'班级数':>6} {'平均班级人数':>10}")
print("-" * 50)
max_hours = ranked[0][1]["hours"] if ranked else 0
for tid, s in ranked:
    bar = "█" * int(s["hours"] / max(1, max_hours) * 30)
    print(f"{s['name']:<12} {s['tasks']:>6} {s['hours']:>8} {len(s['classes']):>6} {bar}")

avg_hours = sum(s["hours"] for _, s in ranked) / max(1, len(ranked))
heavy = [s for _, s in ranked if s["hours"] > avg_hours * 1.5]
print(f"\n平均课时/教师: {avg_hours:.0f}")
print(f"超负荷教师 (>{avg_hours*1.5:.0f} 课时): {len(heavy)} 人")
for s in heavy[:10]:
    print(f"  ⚠️ {s['name']}: {s['hours']} 课时, {s['tasks']} 个任务")

# ── 3. 课时分布 ──
print("\n" + "-" * 60)
print("【课时分布】")
print("-" * 60)

hour_dist = Counter(int(t["total_hours"] or 0) for t in tasks)
for h in sorted(hour_dist):
    bar = "█" * hour_dist[h]
    print(f"  {h:4d} 课时: {hour_dist[h]:4d} 个任务 {bar}")

# ── 4. 课程类型分布 ──
print("\n" + "-" * 60)
print("【课程类型】")
print("-" * 60)
type_dist = Counter(t["course_type"] for t in tasks)
for ct, cnt in type_dist.most_common():
    print(f"  {ct}: {cnt}")

# ── 5. 班级分布 ──
print("\n" + "-" * 60)
print("【班级分布】")
print("-" * 60)
class_task_count = Counter()
for cls_str in task_classes.values():
    for c in cls_str.split(","):
        if c.strip():
            class_task_count[c.strip()] += 1

print(f"总班级数: {len(class_task_count)}")
print(f"平均每班任务数: {sum(class_task_count.values())/len(class_task_count):.1f}")
heavy_classes = [(c, n) for c, n in class_task_count.items() if n > 15]
for c, n in sorted(heavy_classes, key=lambda x: -x[1])[:10]:
    print(f"  ⚠️ {c}: {n} 个任务")

# ── 6. 潜在冲突分析 ──
print("\n" + "-" * 60)
print("【潜在冲突风险】")
print("-" * 60)

# 教师在同一时段不能上两门课 -> 教师课时 / 可用时段
WEEKS = 18
DAYS = 5
SLOTS_PER_DAY = 4  # 默认不排晚课（period 5）
TOTAL_SLOTS = WEEKS * DAYS * SLOTS_PER_DAY  # 18*5*4 = 360

risks = []
for tid, s in ranked:
    # 每个 session = 2 课时 → 每任务 sessions = total_hours / 2
    sessions_needed = s["hours"] // 2
    if sessions_needed > TOTAL_SLOTS:
        risks.append((s["name"], sessions_needed, TOTAL_SLOTS,
                      f"课时 {s['hours']} → 需要 {sessions_needed} 个时段, 但学期只有 {TOTAL_SLOTS} 个可用时段！"))

if risks:
    print("  以下教师课时远超可用时段数：")
    for name, need, have, msg in risks:
        print(f"  ❌ {name}: {msg}")
else:
    print("  ✅ 没有教师超出可用时段上限")

# 教师密度：教师需要占用的 slot 比例
high_density = []
for tid, s in ranked:
    ratio = s["hours"] / 2 / TOTAL_SLOTS
    if ratio > 0.3:
        high_density.append((s["name"], s["hours"], ratio * 100))
if high_density:
    print(f"\n  高密度教师 (占用 >30% 学期时段):")
    for name, hours, pct in sorted(high_density, key=lambda x: -x[2])[:10]:
        print(f"  ⚠️ {name}: {hours} 课时 → 占用 {pct:.0f}% 的可用时段")
else:
    print("  ✅ 教师时段占用比均在合理范围内")

# 教师间交叉分析：两名教师是否经常教同一个班
print("\n" + "-" * 60)
print("【教师-班级密度】")
print("-" * 60)
teacher_class_pairs = Counter()
for t in tasks:
    classes = task_classes.get(t["id"], "")
    for c in classes.split(","):
        if c.strip():
            teacher_class_pairs[(t["teacher_name"], c.strip())] += 1
if teacher_class_pairs:
    most_dense = teacher_class_pairs.most_common(5)
    print("  同一个教师教同一个班多个任务（可能是正常多门课）：")
    for (tname, cls), cnt in most_dense:
        print(f"  {tname} → {cls}: {cnt} 个任务")

print("\n" + "=" * 60)
print("  报告结束")
print("=" * 60)
