"""Room Ranker — 候选空间压缩第二步。

为每个教学任务排序推荐教室。
使用 LightGBM 模型（可用时），否则回退规则版。
"""

from __future__ import annotations

import random

from .model_loader import predict as ml_predict, is_loaded as ml_available

_ML_ENABLED = ml_available()


def rank_rooms(
    task: dict,
    classrooms: list[dict],
    current_room_usage: dict[int, int] | None = None,
    top_k: int = 5,
    diversity_seed: int | None = None,
) -> list[dict]:
    """为单个教学任务排序推荐教室。

    Args:
        task: 教学任务 dict，需含 student_count, required_room_type 等
        classrooms: 教室列表
        current_room_usage: {room_id: current_usage_count} 用于负载均衡
        top_k: 返回前 N 个推荐

    Returns:
        [
            {"room_id": 1, "name": "08108", "score": 0.95,
             "capacity": 80, "capacity_ratio": 0.58, "reasons": ["容量匹配", "类型匹配"]},
            ...
        ]
    """
    if current_room_usage is None:
        current_room_usage = {}

    required_type = _norm(task.get("required_room_type", ""))
    student_count = task.get("student_count", 30)
    scored = []

    for room in classrooms:
        room_id = room.get("id", 0)
        room_type = _norm(room.get("classroom_type", ""))
        capacity = room.get("capacity", 40)
        usage = current_room_usage.get(room_id, 0)

        # 硬约束过滤：类型不匹配或容量不足直接跳过
        if required_type and room_type and required_type != room_type:
            continue
        capacity_ratio = student_count / max(1, capacity)
        if capacity_ratio > 1.0:
            continue

        # 评分
        score = 0.0
        reasons = []

        if required_type:
            score += 20.0
            reasons.append("类型匹配")

        if capacity_ratio >= 0.6:
            score += 30.0 * capacity_ratio
            reasons.append(f"容量合适({capacity_ratio:.0%})")
        elif capacity_ratio >= 0.3:
            score += 20.0 * capacity_ratio
        else:
            score += 10.0 * capacity_ratio

        if usage > 0:
            score -= min(40.0, usage * 8.0)
            reasons.append(f"负载({usage})")
        else:
            score += 10.0

        # ML 增强（模型可用时）
        if _ML_ENABLED:
            features = {
                "teacher_cross_count": task.get("teacher_cross_count", 0),
                "teacher_tasks": task.get("teacher_tasks", 0),
                "student_count": student_count,
                "room_capacity": capacity,
                "capacity_ratio": round(student_count / max(1, capacity), 2),
                "is_early": 0, "is_late": 0, "is_weekend": 0,
                "day_of_week": 0, "period_index": 0, "period_count": 0,
                "teacher_slot_count": 0, "class_slot_count": 0,
                "room_slot_count": 0, "same_day_count": 0,
            }
            ml_score = ml_predict(features)
            score += ml_score * 50  # ML 分数映射到评分空间

        scored.append({
            "room_id": room_id,
            "name": room.get("name", ""),
            "score": round(score, 2),
            "capacity": capacity,
            "capacity_ratio": round(capacity_ratio, 2),
            "usage": usage,
            "reasons": reasons,
        })

    # 多样性偏移：同分情况下不同任务推荐不同教室
    # 当 usage 全为 0 时（新鲜状态），用 room_id 做确定性偏移
    if diversity_seed is not None and all(s["usage"] == 0 for s in scored):
        rng = random.Random(diversity_seed)
        for s in scored:
            s["score"] += rng.uniform(1, 20) * (s["room_id"] % 10) / 10.0

    # 按楼栋分组，尽量每栋楼都有代表，但不强压到 1 个
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in scored:
        prefix = s["name"][:2] if s["name"] else "??"
        groups[prefix].append(s)

    diverse: list[dict] = []
    rng2 = random.Random(diversity_seed) if diversity_seed is not None else random
    keys = list(groups.keys())

    if len(keys) == 1:
        # 单楼栋：直接用全局 top-k
        scored.sort(key=lambda r: -r["score"])
        diverse = scored[:top_k]
    else:
        # 多楼栋：每栋取最优，混合排序
        rng2.shuffle(keys)
        for k in keys:
            group = groups[k]
            group.sort(key=lambda r: -r["score"])
            diverse.append(group[0])
        diverse.sort(key=lambda r: -r["score"])
        diverse = diverse[:top_k]

    return diverse


def _norm(value: str) -> str:
    """规范化类型字符串。"""
    value = (value or "").strip().lower()
    # 简写统一
    replacements = {
        "计算机房": "机房",
        "电脑室": "机房",
        "多媒体教室": "普通教室",
        "阶梯教室": "普通教室",
        "教室": "普通教室",
    }
    return replacements.get(value, value)


def batch_rank_rooms(
    tasks: list[dict],
    classrooms: list[dict],
    top_k: int = 5,
) -> dict[int, list[dict]]:
    """批量排序教室（含自动负载均衡）。"""
    usage: dict[int, int] = {}
    results: dict[int, list[dict]] = {}

    for task in tasks:
        tid = task.get("id", 0)
        ranked = rank_rooms(task, classrooms, usage, top_k)
        results[tid] = ranked

        # 模拟选择最优教室以更新负载
        if ranked:
            best = ranked[0]
            usage[best["room_id"]] = usage.get(best["room_id"], 0) + 1

    return results


# ── 快速验证 ─────────────────────────────────────────
if __name__ == "__main__":
    classrooms = [
        {"id": 1, "name": "08108", "classroom_type": "普通教室", "capacity": 40},
        {"id": 2, "name": "08201", "classroom_type": "普通教室", "capacity": 60},
        {"id": 3, "name": "01106", "classroom_type": "普通教室", "capacity": 80},
        {"id": 4, "name": "93106", "classroom_type": "机房", "capacity": 50},
        {"id": 5, "name": "93502", "classroom_type": "机房", "capacity": 45},
    ]

    tasks = [
        {"id": 1, "required_room_type": "普通教室", "student_count": 35},
        {"id": 2, "required_room_type": "机房", "student_count": 40},
        {"id": 3, "required_room_type": "", "student_count": 60},  # 不限类型
    ]

    print("📊 Room Ranker 验证:")
    for task in tasks:
        print(f"\n  Task {task['id']}: {task['required_room_type'] or '不限类型'} "
              f"({task['student_count']}人)")
        ranked = rank_rooms(task, classrooms, top_k=3)
        for r in ranked:
            print(f"    [{r['room_id']}] {r['name']:8s} 容量={r['capacity']} "
                  f"得分={r['score']:.1f}  {'|'.join(r['reasons'])}")
