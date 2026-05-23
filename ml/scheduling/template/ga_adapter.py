"""GA 模板适配层：连接模板枚举器与 GA 主流程。

每个教学任务从枚举器中选一个模板组合（combo），
combo 内各段的 (day, period, classroom) 用贪心预填充。
GA 只在"每个任务选哪个 combo"层面搜索。

个体 = [combo_index_0, combo_index_1, ...]   ← 对应 tasks 顺序
"""

from __future__ import annotations

import random
from collections import Counter
from time import perf_counter
from typing import Any, Optional

from ml.scheduling.template.enumerator import enumerate_templates
from ml.scheduling.infra.constants import TOTAL_WEEKS


# ── 每个任务的组合 & 预填充 ──────────────────────────────


def build_task_combo_pool(
    task: dict[str, Any],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    task_weeks: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """为一个教学任务构建所有候选 combo 的预填充方案。

    每个 combo 候选 = {
        "combo_index": int,          # 枚举器中的索引
        "segments": [                 # 预填充后的段
            {"weekly": int, "weeks": int, "day": int, "period": int, "classroom_id": int}
        ],
        "total_periods": int,
        "fitness": float,             # 段内预评分（不包含跨任务冲突）
    }
    """
    periods = task.get("_periods_needed") or (int(task.get("total_hours") or 0) // 2)
    if periods <= 0:
        return []

    combos = enumerate_templates(periods, task_weeks=task_weeks)
    if not combos:
        return []

    # 获取可用的 time_slot × classroom
    available = _gather_slot_room_pairs(classrooms, time_slots, task, rng)
    if not available:
        return []

    results: list[dict[str, Any]] = []
    for ci, combo in enumerate(combos):
        segments = _greedy_fill_combo(combo, available, rng)
        if segments is None:
            continue
        total = sum(s["weekly"] * s["weeks"] for s in segments)
        # 段内评分：段级冲突打分（越低越好）
        penalty = _segment_inner_penalty(segments)
        results.append({
            "combo_index": ci,
            "segments": segments,
            "total_periods": total,
            "inner_penalty": penalty,
        })

    # 按 inner_penalty 排序，低的排前面
    results.sort(key=lambda x: x["inner_penalty"])
    return results


def _gather_slot_room_pairs(
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    task: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """收集可用的 (day, period, classroom) 候选对"""
    required_room_type = task.get("_required_room_type") or ""
    total_student_count = int(task.get("total_student_count") or 0)
    bound_classroom_id = task.get("bound_classroom_id")

    # 过滤教室
    valid_rooms = [
        r for r in classrooms
        if int(r.get("capacity") or 0) >= total_student_count
    ]
    if required_room_type:
        valid_rooms = [
            r for r in valid_rooms
            if _is_room_type_match(required_room_type, r.get("classroom_type") or "")
        ]

    if not valid_rooms or not time_slots:
        return []

    # 从 time_slots 提取 (day, period) 集合
    slot_set: set[tuple[int, int]] = set()
    for s in time_slots:
        slot_set.add((int(s["day_of_week"]), int(s["period_index"])))

    # 生成候选对
    pairs: list[dict[str, Any]] = []
    for day, period in sorted(slot_set):
        for room in valid_rooms:
            room_id = int(room["id"])
            pair = {
                "day": day,
                "period": period,
                "classroom_id": room_id,
                "classroom_name": room.get("name") or "",
                "capacity": int(room.get("capacity") or 0),
            }
            pairs.append(pair)

    rng.shuffle(pairs)
    return pairs


def _greedy_fill_combo(
    combo: list[dict[str, int]],
    available: list[dict[str, Any]],
    rng: random.Random,
) -> Optional[list[dict[str, Any]]]:
    """对一个模板组合的每个段贪心选最好的 (day, period, classroom)"""
    segments: list[dict[str, Any]] = []
    used_slots: set[tuple[int, int]] = set()  # (day, period) 段内去重

    for seg in combo:
        weekly = seg["weekly"]
        weeks = seg["weeks"]

        best = None
        best_score = float("inf")

        for _ in range(min(50, len(available))):  # 尝试前50个
            idx = rng.randrange(len(available))
            cand = available[idx]
            slot_key = (cand["day"], cand["period"])
            if slot_key in used_slots:
                continue

            # 评分：偏好大教室留有余量、偏好绑定教室
            score = 0.0
            score += 1.0 / (cand["capacity"] + 1) * 10  # 小教室更易冲突（扣分）
            if cand.get("bound_classroom_id") and cand["classroom_id"] == cand["bound_classroom_id"]:
                score -= 5  # 绑定教室加分

            if score < best_score:
                best_score = score
                best = cand

        if best is None:
            return None  # 该组合不可行

        used_slots.add((best["day"], best["period"]))
        segments.append({
            "weekly": weekly,
            "weeks": weeks,
            "day": best["day"],
            "period": best["period"],
            "classroom_id": best["classroom_id"],
        })

    return segments


def _segment_inner_penalty(segments: list[dict[str, Any]]) -> float:
    """段内惩罚：段之间如果用了相同的 (day, period) 会冲突"""
    slot_weeks: dict[tuple[int, int], int] = {}
    penalty = 0.0
    for seg in segments:
        key = (seg["day"], seg["period"])
        wk = seg["weeks"]
        if key in slot_weeks:
            overlap = min(wk, slot_weeks[key])
            penalty += overlap * 10  # 重叠周数 × 惩罚
        slot_weeks[key] = max(slot_weeks.get(key, 0), wk)
    return penalty


# ── GA 接口 ─────────────────────────────────────────────


def random_individual_template(
    task_pools: list[list[dict[str, Any]]],
    rng: random.Random,
) -> list[int]:
    """生成随机个体：每个任务随机选一个 combo"""
    return [rng.randrange(len(pool)) for pool in task_pools]


def evaluate_individual_template(
    individual: list[int],
    task_pools: list[list[dict[str, Any]]],
    task_ids: list[int],
    total_weeks: int = TOTAL_WEEKS,
) -> dict[str, Any]:
    """评估一个个体：展开所有任务的 combo，检测跨任务冲突。

    Args:
        individual: 每个任务选的 combo_index
        task_pools: 每个任务的候选 combo 列表
        task_ids: 任务 ID 列表（与 individual 顺序对应）
        total_weeks: 学期总周数

    Returns:
        {"fitness": float, "hard_conflict_count": int, ...}
    """
    # 展开所有 combo → 周级分配
    week_assignments: dict[tuple[int, int, int], list[int]] = {}  # (week, day, period) → [task_ids]
    teacher_week_assign: dict[int, dict[tuple[int, int, int], list[int]]] = {}  # teacher → (w,d,p) → [task_ids]
    room_week_assign: dict[int, dict[tuple[int, int, int], list[int]]] = {}
    class_week_assign: dict[int, dict[tuple[int, int, int], list[int]]] = {}

    for task_idx, combo_idx in enumerate(individual):
        task_id = task_ids[task_idx]
        pool = task_pools[task_idx]
        if combo_idx >= len(pool):
            continue
        combo = pool[combo_idx]

        # 按段展开
        week_cursor = 1
        for seg in combo["segments"]:
            w = seg["weekly"]
            wk = seg["weeks"]
            day = seg["day"]
            period = seg["period"]
            room = seg["classroom_id"]

            for week_off in range(wk):
                wn = week_cursor + week_off
                if wn > total_weeks:
                    break
                # 每个 weekly 节数要放在不同的 period 上
                for p_off in range(w):
                    p = period + p_off
                    slot = (wn, day, p)

                    # 全局 slot 占用
                    week_assignments.setdefault(slot, []).append(task_id)

                    # 教师 slot 占用（假设 teacher_id 在 task 里）
                    # 实际上需要 teacher_id 才能做教师冲突检测
                    # 简单版：只检测 slot 冲突

            week_cursor += wk

    # 冲突统计
    hard_conflict_count = 0
    teacher_slot_conflicts = 0
    room_slot_conflicts = 0
    class_slot_conflicts = 0

    for slot, task_list in week_assignments.items():
        if len(task_list) > 1:
            hard_conflict_count += len(task_list) - 1

    # 适应度：冲突越少越好
    fitness = -hard_conflict_count * 1000

    # 软打分：inner_penalty 总和
    inner_penalty = 0
    for task_idx, combo_idx in enumerate(individual):
        pool = task_pools[task_idx]
        if combo_idx < len(pool):
            inner_penalty += pool[combo_idx]["inner_penalty"]
    fitness -= inner_penalty

    return {
        "fitness": fitness,
        "hard_conflict_count": hard_conflict_count,
        "teacher_slot_conflict_count": teacher_slot_conflicts,
        "room_slot_conflict_count": room_slot_conflicts,
        "class_slot_conflict_count": class_slot_conflicts,
        "inner_penalty": inner_penalty,
    }


def crossover_template(
    parent_a: list[int],
    parent_b: list[int],
    rng: random.Random,
) -> list[int]:
    """单点交叉：交换某个任务之后的 combo 选择"""
    n = len(parent_a)
    if n <= 1:
        return parent_a[:]
    point = rng.randrange(1, n)
    child = parent_a[:point] + parent_b[point:]
    return child


def mutate_template(
    individual: list[int],
    task_pools: list[list[dict[str, Any]]],
    mutation_rate: float,
    rng: random.Random,
) -> list[int]:
    """变异：以 mutation_rate 的概率随机重选某个任务的 combo"""
    result = individual[:]
    for i in range(len(result)):
        if rng.random() < mutation_rate:
            pool_size = len(task_pools[i])
            if pool_size > 1:
                result[i] = rng.randrange(pool_size)
    return result


def tournament_select_template(
    scored: list[dict[str, Any]],
    tournament_size: int,
    rng: random.Random,
) -> list[int]:
    """锦标赛选择"""
    n = len(scored)
    if n == 0:
        return []
    selected = [scored[rng.randrange(n)] for _ in range(tournament_size)]
    selected.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
    return selected[0]["individual"]


def evolve_population_template(
    task_pools: list[list[dict[str, Any]]],
    task_ids: list[int],
    rng: random.Random,
    *,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    total_weeks: int = TOTAL_WEEKS,
) -> list[dict[str, Any]]:
    """模板版 GA 进化主循环"""
    # 初始化种群
    population = [
        random_individual_template(task_pools, rng)
        for _ in range(population_size)
    ]

    for gen in range(1, generations + 1):
        scored = [
            {
                "individual": ind,
                "metrics": evaluate_individual_template(ind, task_pools, task_ids, total_weeks),
            }
            for ind in population
        ]
        scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)

        if gen == 1 or gen == generations or gen % 5 == 0:
            m = scored[0]["metrics"]
            print(f"  Gen {gen:3d}: fitness={m['fitness']:.1f}, conflicts={m['hard_conflict_count']}")

        # 精英保留
        elite_count = max(1, min(elite_size, len(scored)))
        next_pop = [item["individual"][:] for item in scored[:elite_count]]

        # 后代生成
        while len(next_pop) < population_size:
            p1 = tournament_select_template(scored, tournament_size, rng)
            p2 = tournament_select_template(scored, tournament_size, rng)
            child = crossover_template(p1, p2, rng)
            child = mutate_template(child, task_pools, mutation_rate, rng)
            next_pop.append(child)

        population = next_pop

    # 最终评估
    scored = [
        {
            "individual": ind,
            "metrics": evaluate_individual_template(ind, task_pools, task_ids, total_weeks),
        }
        for ind in population
    ]
    scored.sort(key=lambda x: x["metrics"]["fitness"], reverse=True)
    return scored


def individual_to_rows(
    individual: list[int],
    task_pools: list[list[dict[str, Any]]],
    task_ids: list[int],
) -> list[dict[str, Any]]:
    """将最优个体展开为 CSV 行（兼容现有输出格式）"""
    rows: list[dict[str, Any]] = []
    seq = 0
    for task_idx, combo_idx in enumerate(individual):
        task_id = task_ids[task_idx]
        pool = task_pools[task_idx]
        if combo_idx >= len(pool):
            continue
        combo = pool[combo_idx]

        week_cursor = 1
        for seg in combo["segments"]:
            w = seg["weekly"]
            wk = seg["weeks"]
            day = seg["day"]
            period = seg["period"]
            room = seg["classroom_id"]

            for week_off in range(wk):
                wn = week_cursor + week_off
                for p_off in range(w):
                    p = period + p_off
                    seq += 1
                    rows.append({
                        "sequence": seq,
                        "teaching_task_id": task_id,
                        "classroom_id": room,
                        "week_number": wn,
                        "day_of_week": day,
                        "period_index": p,
                        "has_hard_conflict": 0,
                        "reject_reason": "",
                    })
            week_cursor += wk

    return rows


def _is_room_type_match(required: str, actual: str) -> bool:
    """判断教室类型是否匹配（简化版）"""
    if not required:
        return True
    if not actual:
        return False
    return required.strip().lower() == actual.strip().lower()
