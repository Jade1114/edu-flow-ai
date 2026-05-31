"""从真实课表构建 LightGBM 训练样本。

正样本：真实课表中被采纳的 (task, slot, classroom) 组合。
负样本：同一 task 可替代但未被采纳的 (slot, classroom) 组合。

输出：training_samples.csv，每行一个 placement 候选。
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "real-dataset"
OUTPUT = DATA / "training_samples.csv"
FIELDS = [
    "label",  # 1=正样本, 0=负样本
    "teacher_cross_count",  # 教师跨班数
    "teacher_tasks",  # 教师任务数
    "student_count",  # 学生人数
    "room_capacity",  # 教室容量
    "capacity_ratio",  # 容量匹配率
    "is_early",  # 是否早课
    "is_late",  # 是否晚课
    "is_weekend",  # 是否周末
    "day_of_week",  # 星期
    "period_index",  # 节次
    "period_count",  # 该(天,节)被用了多少次（热度）
    "teacher_slot_count",  # 该教师在该时段已有安排数
    "class_slot_count",  # 该班级在该时段已有安排数
    "room_slot_count",  # 该教室在该时段已有安排数
    "same_day_count",  # 该教师的课在同一天密度
]


def build():
    print("📦 加载数据...")
    timetables = [json.loads(l) for l in (DATA / "timetables.jsonl").read_text().splitlines() if l.strip()]
    tasks = [json.loads(l) for l in (DATA / "teaching_tasks.jsonl").read_text().splitlines() if l.strip()]
    courses = [json.loads(l) for l in (DATA / "courses.jsonl").read_text().splitlines() if l.strip()]
    classrooms_raw = [json.loads(l) for l in (DATA / "classrooms.jsonl").read_text().splitlines() if l.strip()]
    class_groups_raw = [json.loads(l) for l in (DATA / "class_groups.jsonl").read_text().splitlines() if l.strip()]

    # 索引
    course_map = {c["code"]: c for c in courses}
    teacher_class_count: dict[str, int] = defaultdict(int)
    teacher_task_count: dict[str, int] = defaultdict(int)
    for t in tasks:
        teacher_class_count[t["teacher"]] += 1
        teacher_task_count[t["teacher"]] = len([x for x in tasks if x["teacher"] == t["teacher"]])

    # 生成正负样本
    print("📊 生成样本...")
    samples = []
    rng = random.Random(42)
    period_heat: dict[tuple, int] = defaultdict(int)

    # 先统计时段热度
    for entry in timetables:
        period_heat[(entry.get("day_of_week"), entry.get("period_index"))] += 1

    # 对每个真实排课记录，生成 1 正 + K 负
    for entry in timetables:
        code = entry.get("course_code", "")
        teacher = tasks[0]["teacher"] if tasks else "?"
        class_group = entry.get("class_group", "")

        # 查找匹配的教学任务
        matched_task = None
        for tt in tasks:
            if tt["course_code"] == code and tt["class_group"] == class_group:
                matched_task = tt
                break
        if not matched_task:
            continue

        student_count = 46  # default
        for cg in class_groups_raw:
            if cg["key"] == class_group:
                student_count = cg.get("student_count", 46)
                break

        room_code = entry.get("room", "")
        room_cap = 80
        for cr in classrooms_raw:
            if cr["name"] == room_code:
                room_cap = cr.get("capacity", 80)
                break

        day = entry.get("day", entry.get("day_of_week", 1))
        period = entry.get("period_label", str(entry.get("period_index", 1)))
        if isinstance(period, str) and "-" in period:
            period = int(period.split("-")[0])
        else:
            period = int(period) if period else 1

        teacher_cross = teacher_class_count.get(teacher, 0)
        teacher_tasks = teacher_task_count.get(teacher, 0)
        is_early = 1 if period == 1 else 0
        is_late = 1 if period >= 4 else 0
        is_weekend = 1 if day >= 6 else 0

        def make_sample(label, d, p, cap):
            return {
                "label": label,
                "teacher_cross_count": teacher_cross,
                "teacher_tasks": teacher_tasks,
                "student_count": student_count,
                "room_capacity": cap,
                "capacity_ratio": round(student_count / max(1, cap), 2),
                "is_early": 1 if p == 1 else 0,
                "is_late": 1 if p >= 4 else 0,
                "is_weekend": 1 if d >= 6 else 0,
                "day_of_week": d,
                "period_index": p,
                "period_count": period_heat.get((d, p), 0),
                "teacher_slot_count": 0,
                "class_slot_count": 0,
                "room_slot_count": 0,
                "same_day_count": teacher_tasks if teacher_tasks > 5 else 0,
            }

        # 正样本：真实安排
        pos = make_sample(1, day, period, room_cap)
        samples.append(pos)

        # 负样本：采样 3 个替代位置
        for _ in range(3):
            alt_day = rng.randint(1, 5)
            alt_period = rng.randint(1, 5)
            alt_room = rng.choice(classrooms_raw[:50])
            alt_cap = alt_room.get("capacity", 80)
            if alt_day == day and alt_period == period:
                continue
            neg = make_sample(0, alt_day, alt_period, alt_cap)
            samples.append(neg)

    print(f"✅ 样本数: {len(samples)}")
    print(f"   正样本: {sum(1 for s in samples if s['label'] == 1)}")
    print(f"   负样本: {sum(1 for s in samples if s['label'] == 0)}")

    # 写 CSV
    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for s in samples:
            writer.writerow(s)
    print(f"📄 输出: {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    build()
