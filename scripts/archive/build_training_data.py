#!/usr/bin/env python3
"""
从真实排课数据构建 LightGBM 训练样本。

正样本：真实课表中的 (task, day, period, room) 组合
负样本：同 task 下随机采样的替代 (day, period, room)

输出：data/real-dataset/training_samples.csv
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "real-dataset"
OUTPUT = DATA / "training_samples.csv"

FIELDS = [
    "label",
    "teacher_cross_count", "teacher_tasks",
    "student_count", "room_capacity", "capacity_ratio",
    "is_early", "is_late", "is_weekend",
    "day_of_week", "period_index",
    "period_count",
    "teacher_slot_count", "class_slot_count", "room_slot_count",
    "same_day_count",
]


def load_jsonl(name):
    return [json.loads(l) for l in (DATA / name).read_text().splitlines() if l.strip()]


def build():
    print("📦 加载数据...")
    timetables = load_jsonl("timetables.jsonl")
    tasks = load_jsonl("teaching_tasks.jsonl")
    courses = {c["code"]: c for c in load_jsonl("courses.jsonl")}
    classrooms_list = load_jsonl("classrooms.jsonl")
    classrooms_map = {cr["name"]: cr for cr in classrooms_list}
    candidate_rooms = [cr for cr in classrooms_list if cr.get("classroom_type") in ("普通教室", "机房")]
    class_groups = {cg["name"]: cg for cg in load_jsonl("class_groups.jsonl")}

    # 索引：教学任务 by (course_code, class_group) → teacher
    task_map = {}
    for tt in tasks:
        key = (tt["course_code"], tt["class_group"])
        if key not in task_map:
            task_map[key] = tt

    # 统计：教师跨班数 / 任务数
    teacher_class_count = defaultdict(set)
    teacher_task_count = defaultdict(int)
    for tt in tasks:
        teacher_class_count[tt["teacher"]].add(tt["class_group"])
        teacher_task_count[tt["teacher"]] += 1

    # 统计：每个 (day, period) 的热度
    period_heat = defaultdict(int)
    for entry in timetables:
        period_heat[(entry["day"], entry["period_start"])] += 1

    print(f"  排课记录: {len(timetables)}")
    print(f"  教学任务: {len(tasks)}")
    print()

    rng = random.Random(42)
    samples = []

    for entry in timetables:
        code = entry["course_code"]
        class_group = entry["class_group"]
        week = entry["week"]
        day = entry["day"]
        period = entry["period_start"]
        room_code = entry.get("room", "")

        # 找到对应的教学任务
        matched = task_map.get((code, class_group))
        if not matched:
            continue
        teacher = matched["teacher"]
        total_hours = matched.get("total_hours", 32)
        total_lessons = int(total_hours) // 2  # 每节 2 课时

        # 学生数
        cg = class_groups.get(class_group, {})
        student_count = cg.get("student_count", 46)

        # 教室容量
        cr = classrooms_map.get(room_code, {})
        room_cap = cr.get("capacity", 80)

        # 教师统计
        teacher_cross = len(teacher_class_count.get(teacher, set()))
        teacher_tasks = teacher_task_count.get(teacher, 0)

        # 时段特征
        is_early = 1 if period == 1 else 0
        is_late = 1 if period >= 4 else 0
        is_weekend = 1 if day >= 6 else 0

        def make_sample(label, d, p, cap, teacher_cross, teacher_tasks):
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

        # 正样本：真实的排课决定
        pos = make_sample(1, day, period, room_cap, teacher_cross, teacher_tasks)
        samples.append(pos)

        # 负样本：同一任务下 N 个替代候选
        alt_rooms = [cr for cr in candidate_rooms if cr.get("name") != room_code]
        neg_count = min(5, len(alt_rooms))
        chosen_rooms = rng.sample(alt_rooms, neg_count) if alt_rooms else []

        for alt_room in chosen_rooms:
            alt_day = rng.randint(1, 5)
            alt_period = rng.randint(1, 5)
            if alt_day == day and alt_period == period:
                continue
            alt_cap = alt_room.get("capacity", 80)
            neg = make_sample(0, alt_day, alt_period, alt_cap, teacher_cross, teacher_tasks)
            samples.append(neg)

    print(f"✅ 样本数: {len(samples)}")
    pos_count = sum(1 for s in samples if s["label"] == 1)
    print(f"   正样本: {pos_count}")
    print(f"   负样本: {len(samples) - pos_count}")

    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(samples)
    print(f"📄 输出: {OUTPUT}")


if __name__ == "__main__":
    build()
