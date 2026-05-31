"""Room Ranker — 候选空间压缩第二步。

为每个教学任务排序推荐教室（规则版，后续可升级为 LightGBM）。

评分维度：
1. 容量匹配     — 教室容量 ≥ 学生数，且不过度浪费
2. 类型匹配     — 普通教室/机房/体育场匹配
3. 负载均衡     — 优先推荐当前使用率低的教室
"""

from __future__ import annotations


def rank_rooms(
    task: dict,
    classrooms: list[dict],
    current_room_usage: dict[int, int] | None = None,
    top_k: int = 5,
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

        reasons = []
        score = 0.0

        # 1. 类型匹配（硬条件：不匹配则排除）
        if required_type and room_type and required_type != room_type:
            continue  # 类型不匹配，跳过
        if required_type:
            score += 20.0
            reasons.append("类型匹配")

        # 2. 容量匹配
        capacity_ratio = student_count / max(1, capacity)
        if capacity_ratio > 1.0:
            continue  # 教室装不下，跳过

        if capacity_ratio >= 0.6:
            score += 30.0 * capacity_ratio
            reasons.append(f"容量合适({capacity_ratio:.0%})")
        elif capacity_ratio >= 0.3:
            score += 20.0 * capacity_ratio
            reasons.append(f"容量偏松({capacity_ratio:.0%})")
        else:
            score += 10.0 * capacity_ratio
            reasons.append(f"容量过松({capacity_ratio:.0%})")

        # 3. 负载均衡（使用率越低越好）
        if usage > 0:
            load_penalty = min(15.0, usage * 2.0)
            score -= load_penalty
        else:
            score += 5.0  # 未使用的教室有加分
            reasons.append("空闲教室")

        scored.append({
            "room_id": room_id,
            "name": room.get("name", ""),
            "score": round(score, 2),
            "capacity": capacity,
            "capacity_ratio": round(capacity_ratio, 2),
            "usage": usage,
            "reasons": reasons,
        })

    scored.sort(key=lambda r: -r["score"])
    return scored[:top_k]


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
