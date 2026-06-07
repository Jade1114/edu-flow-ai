#!/usr/bin/env python3
"""
检查 Placement Model 推出来的候选质量和多样性。

问题：模型推的 top-k 候选是不是太相似了？
比如所有任务都被推荐到"周一第1-2节"，导致 CP-SAT 怎么排都会冲突。
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from app.ml.placement_direct import DirectPlacementModel, direct_features
from app.db.session import connect, load_db_config

PARSED_DIR = Path(__file__).resolve().parents[2] / "data" / "parsed"

def load_teaching_tasks_from_db():
    """从 DB 读教学任务"""
    db = load_db_config()
    conn = connect(db)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tt.id, tt.total_hours, c.code AS course_code, c.name AS course_name,
                       c.course_type, t.name AS teacher_name, t.department
                FROM teaching_task tt
                JOIN course c ON c.id = tt.course_id
                JOIN teacher t ON t.id = tt.primary_teacher_id
                WHERE tt.status = 'ACTIVE'
                ORDER BY tt.id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("Placement Model 候选质量 & 多样性检查")
    print("=" * 60)

    # 1. 加载模型
    print("\n[1/4] 加载模型...")
    m = DirectPlacementModel.load()
    print(f"  模型类别数: {len(m.resource_by_label)}")
    print(f"  特征数: {len(m.features)}")

    # 2. 加载教学任务
    print("\n[2/4] 加载教学任务...")
    tasks = load_teaching_tasks_from_db()
    print(f"  教学任务: {len(tasks)}")

    # 3. 模型推理
    print("\n[3/4] 模型推理 TopK 候选...")
    TOP_K = 30
    all_predictions = []

    for t in tasks:
        task_like = {
            "course_name": t["course_name"],
            "course_code": t["course_code"],
            "teacher_no": "",
            "teacher_name": t["teacher_name"],
            "class_name": "",
            "class_major": "",
            "class_department": t["department"],
            "class_grade": 0,
            "student_count": 0,
            "total_hours": t["total_hours"],
            "course_type": t["course_type"],
            "required_room_type": "",
        }
        row = direct_features(task_like)
        frame = pd.DataFrame([row], columns=m.features)
        topk = m.predict_topk(task_like, top_k=TOP_K)
        all_predictions.append({
            "task_id": t["id"],
            "teacher": t["teacher_name"],
            "course": t["course_name"],
            "topk": topk,
        })

    print(f"  共推理 {len(all_predictions)} 个任务, 每任务 top-{TOP_K}")

    # 4. 多样性分析
    print("\n[4/4] 多样性分析...")

    # 4a. 解析 resource_key = "room|day|period"
    slot_counter = Counter()       # 每个 (day, period) 被推荐了多少次
    room_counter = Counter()       # 每个 room 被推荐了多少次
    day_counter = Counter()        # 每天被推荐了多少次
    period_counter = Counter()     # 每节次被推荐了多少次
    full_key_counter = Counter()   # 完整 resource_key 被推荐了多少次
    teacher_slot_matrix = defaultdict(set)  # 教师 → 被推荐的 slots

    for pred in all_predictions:
        for key, score in pred["topk"]:
            parts = key.split("|")
            if len(parts) == 3:
                room, day, period = parts
            else:
                continue
            slot_counter[(int(day), int(period))] += 1
            room_counter[room] += 1
            day_counter[int(day)] += 1
            period_counter[int(period)] += 1
            full_key_counter[key] += 1
            teacher_slot_matrix[pred["teacher"]].add((int(day), int(period)))

    total_recs = sum(slot_counter.values())

    print(f"\n  --- 时段热度分布 ---")
    print(f"  {'星期':>4} {'节次':>4} {'被推荐次数':>10} {'占比':>8}")
    for (day, period), count in slot_counter.most_common(15):
        pct = count / total_recs * 100
        day_name = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"][day]
        print(f"  {day_name:>4} 第{period}节  {count:>8}  {pct:>6.1f}%")

    print(f"\n  --- 教室热度 Top 10 ---")
    for room, count in room_counter.most_common(10):
        pct = count / total_recs * 100
        print(f"  {room:>8}: {count:>6} 次 ({pct:.1f}%)")

    print(f"\n  --- 模型多样性指标 ---")
    # 有多少不同的 resource_key 被推荐
    unique_keys = len(full_key_counter)
    total_keys_possible = TOP_K * len(all_predictions)
    diversity_ratio = unique_keys / total_keys_possible
    print(f"  总推荐次数: {total_recs}")
    print(f"  不同 resource_key 数: {unique_keys}")
    print(f"  多样性比例: {diversity_ratio:.4f} (1.0 = 全部不同, 越接近1越好)")

    # 最热门资源被多少任务推荐
    most_hot_key, most_hot_count = full_key_counter.most_common(1)[0]
    print(f"\n  最热门资源: {most_hot_key} (被推荐 {most_hot_count} 次, "
          f"{most_hot_count/len(all_predictions)*100:.1f}% 的任务把它作为 top-{TOP_K})")

    # 前 5 热门资源占总量比例
    top5_hot = full_key_counter.most_common(5)
    top5_total = sum(c for _, c in top5_hot)
    print(f"  Top5 热门资源占总推荐: {top5_total/total_recs*100:.1f}%")

    # 教师 slot 多样性
    teacher_slot_counts = [len(slots) for slots in teacher_slot_matrix.values()]
    if teacher_slot_counts:
        avg_slots_per_teacher = sum(teacher_slot_counts) / len(teacher_slot_counts)
        print(f"\n  教师人均被推荐的时段数: {avg_slots_per_teacher:.1f} "
              f"(最多{max(teacher_slot_counts)}, 最少{min(teacher_slot_counts)})")

    # 时段 Gini 系数（衡量时段推荐集中度）
    slot_values = sorted(slot_counter.values())
    n = len(slot_values)
    if n > 1:
        cum = 0
        for i, v in enumerate(slot_values):
            cum += (i + 1) * v
        gini = (2 * cum / (n * sum(slot_values))) - (n + 1) / n
        print(f"  时段推荐 Gini 系数: {gini:.4f} (0=完全均匀, 1=完全集中)")

    # 结论
    print(f"\n  --- 诊断结论 ---")
    if diversity_ratio < 0.3:
        print(f"  ⚠️ 候选多样性偏低 ({diversity_ratio:.2f})，大量任务推荐了相同的资源点")
    elif diversity_ratio < 0.6:
        print(f"  😐 候选多样性一般 ({diversity_ratio:.2f})，有一定集中度")
    else:
        print(f"  ✅ 候选多样性不错 ({diversity_ratio:.2f})")

    if top5_total / total_recs > 0.3:
        print(f"  ⚠️ Top5 热门资源占了 {top5_total/total_recs*100:.1f}%，候选过于集中")
    else:
        print(f"  ✅ Top5 热度占比 {top5_total/total_recs*100:.1f}%，分布较合理")


if __name__ == "__main__":
    main()
